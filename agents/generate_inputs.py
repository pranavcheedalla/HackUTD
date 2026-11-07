"""Phase 3 helper - test inputs. Nemotron Super proposes input lines that hit every branch.

    generate_inputs(spec, cobol_src) -> list[str]    (20-30 lines, each one ACCEPT line)

After each call, LAST_RUN holds {"cases": [{input, covers}], "warnings": [...]} so the
eval script (or the UI) can show why each input exists.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from agents import _llm
from agents.cobol_static import analyze, numbered, render_summary

MODEL = "super"
MIN_CASES, MAX_CASES = 20, 30

# ----------------------------------------------------------------------------- PROMPTS
GENERATE_INPUTS_SYSTEM = """\
You are a QA engineer writing characterization tests for a legacy COBOL program. Each test
is ONE line of text fed to the program's ACCEPT; the program's real output becomes the
expected result, so your job is coverage, not predicting outputs.

Every input line MUST match the program's exact input format:
- Fixed-width records: every field at its exact columns, numbers zero-padded on the left,
  NO decimal point for V (implied decimal) fields: PIC 9(5)V99 value 123.45 -> "0012345".
  The line length must equal the record width unless the case is deliberately short/long.
- Text fields (PIC X) are padded on the right with spaces to their width.
- If the program parses a delimited line instead, follow that delimiter exactly.

Cover ALL of these (one case can cover several):
1. 3-5 typical, realistic business cases.
2. Zero in each numeric field (one at a time), and all-zero input.
3. Maximum value of each numeric field (all 9s) and the minimum non-zero value (…01).
4. Every IF / EVALUATE / WHEN branch, including WHEN OTHER, and values exactly on,
   one below and one above each numeric threshold.
5. Each 88-level / code value, plus one invalid code.
6. Truncation / rounding: values whose result has more decimals than the receiving field,
   e.g. results ending in .xx5 and .xx9, to expose truncation vs rounding.
7. Overflow: inputs whose computed results exceed the receiving field's digits.
8. Negative / invalid data: a '-' or letters in a numeric field, spaces in a numeric field,
   a short line and an over-long line (just 1-2 of these; the COBOL output is recorded as-is).
Return {min_cases}-{max_cases} cases, each with a short "covers" note (under 15 words).
No duplicates. Keep the whole reply compact: no explanations outside the JSON.
"""

GENERATE_INPUTS_USER = """\
SPEC:
{spec}

STATIC ANALYSIS (computed by a parser - field columns and widths are exact):
{static}

COBOL SOURCE:
{source}
"""

GENERATE_INPUTS_MORE = """\

You returned only {count} usable cases (need at least {min_cases}). Already have:
{existing}
Return {need} MORE distinct cases covering what is still missing, same JSON format.
"""
# -----------------------------------------------------------------------------

INPUTS_SCHEMA = {
    "type": "object",
    "required": ["cases"],
    "properties": {
        "cases": {
            "type": "array",
            "maxItems": MAX_CASES,
            "items": {
                "type": "object",
                "required": ["input", "covers"],
                "properties": {"input": {"type": "string", "maxLength": 300},
                               "covers": {"type": "string", "maxLength": 160}},
            },
        }
    },
}

LAST_RUN: dict = {"cases": [], "warnings": []}


def _cases(raw) -> list[dict]:
    if isinstance(raw, str):
        from agents._json import extract_json

        try:
            raw = extract_json(raw)
        except ValueError:
            return []
    if isinstance(raw, dict):
        raw = raw.get("cases") or raw.get("inputs") or []
    out = []
    for c in raw if isinstance(raw, list) else []:
        if isinstance(c, str):
            out.append({"input": c, "covers": ""})
        elif isinstance(c, dict) and isinstance(c.get("input"), (str, int)):
            out.append({"input": str(c["input"]), "covers": str(c.get("covers", ""))})
    return out


def _clean(cases: list[dict], width: int, warnings: list[str]) -> list[dict]:
    seen, out = set(), []
    for c in cases:
        line = c["input"].rstrip("\r\n")
        if "\n" in line or "\r" in line:
            warnings.append(f"dropped multi-line input {line!r}")
            continue
        if line in seen:
            continue
        seen.add(line)
        if width and len(line) != width and "short" not in c["covers"].lower() and "long" not in c["covers"].lower():
            warnings.append(f"width {len(line)} != record width {width}: {line!r} ({c['covers']})")
        out.append({"input": line, "covers": c["covers"]})
    return out


def _baseline(analysis) -> list[dict]:
    """Deterministic cases added for unsigned numeric fixed-width records: all zeros, all nines."""
    if _anchors(analysis):
        # Hold onto failures found by the fresh-input audit, not just arithmetic examples.
        special = {
            'interest': [' 001 | 050 | 01 ', '00001|000.01|01', '1\t|2|3', '1.|2|3', 'abc|5|1'],
            'invoice': ['2|99980.00|49.99', ' 001 | 00012.35 | 000.01 ', '1\t|2|3', '1|1.|0', 'abc|10|0'],
            'payroll': ['0.01|4.95', ' 040.00 | 020.00 ', '1\t|2', '1.|2', 'abc|10'],
        }
        return [{'input': line, 'covers': 'audit regression: validation, whitespace, leading zeros or cent boundary'}
                for line in special[analysis.program_id.lower()]]
    lay = analysis.input_layout
    if not lay or not all(f["pic"] and set(f["pic"].replace("(", "").replace(")", "")) <= set("9V0123456789")
                          for f in lay):
        return []
    w = analysis.input_width
    return [{"input": "0" * w, "covers": "baseline: every field zero"},
            {"input": "9" * w, "covers": "baseline: every field at its maximum"}]


def _fallback_cases(analysis) -> list[dict]:
    """No-LLM boundary cases: vary one field at a time (min / one / max, or blank / filled)."""
    lay, w = analysis.input_layout, analysis.input_width
    if not lay or not w:
        return []

    def numeric(f):
        return set((f["pic"] or "X").replace("(", "").replace(")", "")) <= set("9V0123456789S")

    def width(f):
        return f["end"] - f["start"] + 1

    base = {f["name"]: ("0" * (width(f) - 1) + "1") if numeric(f) else "A" * width(f) for f in lay}
    variants = [("typical: every numeric field 1", {})]
    for f in lay:
        n = width(f)
        opts = [("0" * n, "zero"), ("9" * n, "maximum")] if numeric(f) else [(" " * n, "blank"), ("Z" * n, "other letters")]
        variants += [(f"{f['name']} {label}", {f["name"]: v}) for v, label in opts]
    out = []
    for covers, override in variants:
        rec = "".join(override.get(f["name"], base[f["name"]]) for f in lay).ljust(w)[:w]
        out.append({"input": rec, "covers": f"fallback: {covers}"})
    return out


def _anchors(analysis) -> list[dict]:
    """Protect the reviewed P2 examples; fixed-width P3 samples use their own protocol."""
    module_id = (analysis.program_id or "").lower()
    root = Path(__file__).resolve().parents[1]
    canonical = root / "legacy" / f"{module_id}.cbl"
    if analysis.delimiter != "|" or module_id not in {"interest", "payroll", "invoice"} or not canonical.is_file():
        return []
    expected = analyze(canonical.read_text())
    if analysis.delimited_fields != expected.delimited_fields:
        return []
    values = json.loads((root / "legacy" / "inputs" / f"{module_id}.json").read_text())
    return [{"input": value, "covers": "reviewed handwritten regression case"} for value in values]


def _call(system: str, user: str, schema: dict):
    """call_llm, but a failed call (timeout, bad JSON, 5xx) becomes "" so the fallbacks run."""
    try:
        return _llm.call_llm(MODEL, system, user, schema)
    except Exception as exc:  # noqa: BLE001 - the pipeline must keep going
        if os.getenv("LLM_MODE", "real").lower() == "real":
            raise
        print(f"[{__name__}] LLM call failed, using fallback: {exc!r}"[:300], file=sys.stderr)
        return ""


def generate_inputs(spec: dict, cobol_src: str) -> list[str]:
    analysis = analyze(cobol_src)
    anchors = _anchors(analysis)
    # Reviewed cases already fill part of the budget; ask only for the remainder so the
    # model's reply stays small (unbounded replies were truncated into invalid JSON).
    want_min = max(5, MIN_CASES - len(anchors))
    want_max = max(want_min, MAX_CASES - len(anchors))
    system = GENERATE_INPUTS_SYSTEM.format(min_cases=want_min, max_cases=want_max)
    user = GENERATE_INPUTS_USER.format(spec=json.dumps(spec, indent=1), static=render_summary(analysis),
                                       source=numbered(cobol_src))
    warnings: list[str] = []

    proposals = _clean(_cases(_call(system, user, INPUTS_SCHEMA)), analysis.input_width, warnings)
    if analysis.delimiter:
        # Keep deliberately malformed cases, but reject the old padded-buffer fallback.
        proposals = [c for c in proposals if len(c['input']) < 256]
    if os.getenv('LLM_MODE', 'real').lower() == 'real' and not proposals:
        raise ValueError('Model returned no usable input proposals')
    cases = _clean(anchors + proposals, analysis.input_width, warnings)
    if len(cases) < MIN_CASES:
        need = MIN_CASES - len(cases)
        more_user = user + GENERATE_INPUTS_MORE.format(
            count=len(cases), min_cases=MIN_CASES, need=need,
            existing="\n".join(f"- {c['input']!r}  ({c['covers']})" for c in cases) or "(none)")
        extra = _cases(_call(system, more_user, INPUTS_SCHEMA))
        cases = _clean(cases + extra, analysis.input_width, warnings)
        if len(cases) < MIN_CASES:
            warnings.append(f"only {len(cases)} cases after retry")

    if not cases:
        warnings.append("model gave no usable cases; using deterministic boundary cases")
        cases = _clean(_fallback_cases(analysis), analysis.input_width, warnings)
    # Baselines belong inside the limit, and reviewed cases cannot be displaced.
    cases = _clean(anchors + _baseline(analysis) + cases, analysis.input_width, warnings)[:MAX_CASES]
    if os.getenv("LLM_MODE", "real").lower() == "real" and len(cases) < MIN_CASES:
        raise ValueError(f"Only {len(cases)} distinct inputs; require {MIN_CASES}-{MAX_CASES}")

    for w in warnings:
        print(f"[generate_inputs] {w}", file=sys.stderr)
    LAST_RUN.clear()
    LAST_RUN.update(cases=cases, warnings=warnings)
    return [c["input"] for c in cases]
