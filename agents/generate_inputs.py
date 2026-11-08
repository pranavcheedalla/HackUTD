"""Phase 3 helper - test inputs. Nemotron Super proposes input lines that hit every branch.

    generate_inputs(spec, cobol_src) -> list[str]    (20-30 lines, each one ACCEPT line)

After each call, LAST_RUN holds {"cases": [{input, covers}], "warnings": [...]} so the
eval script (or the UI) can show why each input exists.
"""
from __future__ import annotations

import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

from agents import _llm
from agents.cobol_static import analyze, kw, numbered, render_summary, strip_comments

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
- A SUBPROGRAM (no ACCEPT; PROCEDURE DIVISION USING) is run through a test driver: each
  line is the parameters in USING order separated by "|" (exactly one fewer "|" than
  parameters), numbers typed with a literal decimal point ("1000.00"), text as-is.
  An empty token is allowed (number -> 0, text -> spaces).

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


RECORD_NOTE = """

THIS PROGRAM READS A FIXED-WIDTH RECORD. Do NOT type the record yourself (column counting is
error-prone). For every case return "values": one human-readable value per field, in exactly
this order:
{fields}
Numbers as plain decimals (e.g. "500.00", "2", "0"), no padding and no implied-decimal digits;
text fields as the literal characters (e.g. "G"). A program-side formatter builds the exact
record. Values that cannot fit a field are dropped, so stay within each field's range.
"""

RECORD_SCHEMA = {
    "type": "object",
    "required": ["cases"],
    "properties": {"cases": {"type": "array", "maxItems": MAX_CASES, "items": {
        "type": "object", "required": ["values", "covers"],
        "properties": {"values": {"type": "array", "maxItems": 40, "items": {"type": "string", "maxLength": 80}},
                       "covers": {"type": "string", "maxLength": 160}}}}},
}


def _record_mode(analysis) -> bool:
    """Fixed-width ACCEPT record: the model gives field values and code builds the columns."""
    return bool(analysis.input_layout) and not analysis.delimiter and getattr(analysis, "kind", "program") != "subprogram"


def _record_fields(analysis) -> str:
    rows = []
    for f in analysis.input_layout:
        leaf = analysis.index.get(f["name"])
        if leaf is not None and leaf.kind == "numeric":
            top = Decimal(10) ** leaf.int_digits - Decimal(1).scaleb(-leaf.decimals)
            kind = f"number 0..{top}" + (f", up to {leaf.decimals} decimals" if leaf.decimals else ", whole")
        else:
            kind = f"text, {f['length']} character(s)"
        codes = "; codes: " + ", ".join(f"{n}={v}" for n, v in f["conditions"]) if f["conditions"] else ""
        rows.append(f"  {len(rows) + 1}. {f['name']}: {kind}{codes}")
    return "\n".join(rows)


def _encode_record(values: list, analysis, warnings: list[str]) -> str | None:
    """Build the exact fixed-width line from per-field values; None if a value cannot fit."""
    if len(values) != len(analysis.input_layout):
        warnings.append(f"dropped record case with {len(values)} values for {len(analysis.input_layout)} fields")
        return None
    out = []
    for f, raw in zip(analysis.input_layout, values):
        raw = str(raw)
        leaf = analysis.index.get(f["name"])
        if leaf is not None and leaf.kind == "numeric":
            try:
                value = Decimal(raw.strip() or "0")
            except ArithmeticError:
                warnings.append(f"dropped record case: {f['name']}={raw!r} is not a number")
                return None
            scaled = value.scaleb(leaf.decimals)
            if value < 0 or scaled != scaled.to_integral_value() or scaled >= Decimal(10) ** f["length"]:
                warnings.append(f"dropped record case: {f['name']}={raw!r} does not fit {leaf.pic}")
                return None
            out.append(str(int(scaled)).zfill(f["length"]))
        else:
            out.append(raw[:f["length"]].ljust(f["length"]))
    return "".join(out)


def _record_grid(analysis) -> list[dict]:
    """Deterministic valid records (zero / smallest / one / middle / max per numeric field,
    each 88-level code plus an invalid one per text field) to top up a short model answer."""
    from itertools import product
    options = []
    for f in analysis.input_layout:
        leaf = analysis.index.get(f["name"])
        if leaf is not None and leaf.kind == "numeric":
            top = Decimal(10) ** leaf.int_digits - Decimal(1).scaleb(-leaf.decimals)
            unit = Decimal(1).scaleb(-leaf.decimals)
            options.append([str(v) for v in dict.fromkeys(
                [Decimal(1), (top / 2).quantize(unit), top, Decimal(0), unit])])
        else:
            codes = [v.strip("'\"") for _, v in f["conditions"]]
            options.append(list(dict.fromkeys([*codes, "Z", " "])))
    cases, sink = [], []
    for combo in product(*options):
        line = _encode_record(list(combo), analysis, sink)
        if line is not None:
            cases.append({"input": line, "covers": "deterministic boundary record: " + ", ".join(combo)})
        if len(cases) >= MAX_CASES:
            break
    return cases


def _record_cases(raw, analysis, warnings: list[str]) -> list[dict]:
    """Field-value cases are encoded; ready-made "input" lines are still accepted as before."""
    items = raw.get("cases") or raw.get("inputs") or [] if isinstance(raw, dict) else raw
    out = []
    for c in items if isinstance(items, list) else []:
        if isinstance(c, dict) and isinstance(c.get("values"), list):
            line = _encode_record(c["values"], analysis, warnings)
            if line is not None:
                out.append({"input": line, "covers": str(c.get("covers", ""))})
        else:
            out += _cases([c])
    return out


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


_CMP = (r"\s*(?:IS\s+)?(?:NOT\s+)?(?:>=|<=|=|>|<|EQUAL(?:\s+TO)?|GREATER(?:\s+THAN)?(?:\s+OR\s+EQUAL(?:\s+TO)?)?"
        r"|LESS(?:\s+THAN)?(?:\s+OR\s+EQUAL(?:\s+TO)?)?)\s*('[^'\n]*'|\"[^\"\n]*\"|[+-]?\d+(?:\.\d+)?)")


def _compared_values(src: str, name: str) -> list[str]:
    """Literals a param is compared against in IF/WHEN conditions (and its 88-level values)."""
    text = strip_comments(src)
    pm = re.search(kw("PROCEDURE") + r"\s+DIVISION", text, re.I)
    proc = text[pm.end():] if pm else ""
    out = [m.group(1) for m in re.finditer(kw(re.escape(name)) + _CMP, proc, re.I)]
    out += [m.group(1) for m in re.finditer(r"('[^'\n]*'|\"[^\"\n]*\"|[+-]?\d+(?:\.\d+)?)\s*(?:<=|>=|=|<|>)\s*"
                                            + kw(re.escape(name)), proc, re.I)]
    return list(dict.fromkeys(out))


def _num(value: Decimal, p: dict) -> str:
    return f"{value:.{p['dec_digits']}f}"


def _driver_cases(analysis, src: str) -> list[dict]:
    """No-LLM driver-format cases for a subprogram: every compared literal, each threshold
    just below / at / just above, zero, maximum, invalid/lowercase codes and empty tokens."""
    params = analysis.params
    if analysis.kind != "subprogram" or not params:
        return []
    found = {p["name"]: _compared_values(src, p["name"]) for p in params}
    for p in params:  # 88-level values count as compared literals too
        f = analysis.index.get(p["name"])
        for _, raw in (f.conditions if f else []):
            found[p["name"]] += re.findall(r"'[^']*'|\"[^\"]*\"|[+-]?\d+(?:\.\d+)?", raw)

    def text_values(p):
        return [v[1:-1][:p["length"]] for v in found[p["name"]] if v[:1] in "'\""]

    def invalid_code(p):
        codes = text_values(p)
        return next((c for c in ("X", "Z", "Q", "9") if c not in codes), "?") * min(p["length"], 1)

    # Held-constant values fall THROUGH every code check, so a numeric threshold branch
    # (e.g. WHEN LK-SUBTOTAL >= 1000.00 after WHEN LK-TIER = 'G') is actually reached.
    base = {}
    for p in params:
        if p["kind"] == "text":
            base[p["name"]] = invalid_code(p)
        else:
            base[p["name"]] = _num(Decimal(1), p) if p["int_digits"] else _num(Decimal("0.5"), p)

    cases: list[tuple[str, dict]] = [("every param typical", {}), ("every token empty", {p["name"]: "" for p in params})]
    for p in params:
        name = p["name"]
        if p["kind"] == "text":
            codes = text_values(p)
            cases += [(f"{name} = {c!r} branch", {name: c}) for c in codes]
            if codes and codes[0].lower() != codes[0]:
                cases.append((f"{name} lowercase {codes[0].lower()!r} (codes are case-sensitive)", {name: codes[0].lower()}))
            cases.append((f"{name} invalid code {invalid_code(p)!r} (OTHER branch)", {name: invalid_code(p)}))
            cases.append((f"{name} empty (spaces)", {name: ""}))
            continue
        ulp = Decimal(1).scaleb(-p["dec_digits"])
        maximum = Decimal("9" * p["int_digits"] + ("." + "9" * p["dec_digits"] if p["dec_digits"] else "") or "0")
        for raw in found[name]:
            if raw[:1] in "'\"":
                continue
            t = Decimal(raw)
            for v, label in ((t - ulp, "just below"), (t, "at"), (t + ulp, "just above")):
                if 0 <= v <= maximum or (p["signed"] and -maximum <= v <= maximum):
                    cases.append((f"{name} {label} threshold {raw}", {name: _num(v, p)}))
        cases += [(f"{name} zero", {name: _num(Decimal(0), p)}), (f"{name} maximum", {name: _num(maximum, p)}),
                  (f"{name} empty (NUMVAL -> 0)", {name: ""})]
        if p["signed"]:
            cases.append((f"{name} negative", {name: _num(-Decimal(1), p)}))
    out = []
    for covers, override in cases:
        line = "|".join(override.get(p["name"], base[p["name"]]) for p in params)
        out.append({"input": line, "covers": f"driver: {covers}"})
    return out


def _driver_format_ok(line: str, analysis) -> bool:
    return analysis.kind != "subprogram" or line.count("|") == len(analysis.params) - 1


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


def _keep_driver_format(cases: list[dict], analysis, warnings: list[str]) -> list[dict]:
    kept = [c for c in cases if _driver_format_ok(c["input"], analysis)]
    for c in cases:
        if c not in kept:
            warnings.append(f"dropped {c['input']!r}: driver lines need exactly {len(analysis.params) - 1} '|'")
    return kept


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

    records = _record_mode(analysis)
    if records:
        system += RECORD_NOTE.format(fields=_record_fields(analysis))

    def ask(prompt: str) -> list[dict]:
        if records:
            return _record_cases(_call(system, prompt, RECORD_SCHEMA), analysis, warnings)
        return _cases(_call(system, prompt, INPUTS_SCHEMA))

    proposals = _clean(ask(user), analysis.input_width, warnings)
    if analysis.delimiter:
        # Keep deliberately malformed cases, but reject the old padded-buffer fallback.
        proposals = [c for c in proposals if len(c['input']) < 256]
    proposals = _keep_driver_format(proposals, analysis, warnings)
    if os.getenv('LLM_MODE', 'real').lower() == 'real' and not proposals:
        raise ValueError('Model returned no usable input proposals')
    cases = _clean(anchors + proposals, analysis.input_width, warnings)
    if len(cases) < MIN_CASES:
        need = MIN_CASES - len(cases)
        more_user = user + GENERATE_INPUTS_MORE.format(
            count=len(cases), min_cases=MIN_CASES, need=need,
            existing="\n".join(f"- {c['input']!r}  ({c['covers']})" for c in cases) or "(none)")
        extra = _keep_driver_format(ask(more_user), analysis, warnings)
        cases = _clean(cases + extra, analysis.input_width, warnings)
        if len(cases) < MIN_CASES and records:
            warnings.append(f"only {len(cases)} model cases after retry; adding deterministic boundary records")
            cases = _clean(cases + _record_grid(analysis), analysis.input_width, warnings)
        if len(cases) < MIN_CASES:
            warnings.append(f"only {len(cases)} cases after retry")

    driver_cases = _driver_cases(analysis, cobol_src)  # [] unless this is a subprogram
    if not cases and not driver_cases:
        warnings.append("model gave no usable cases; using deterministic boundary cases")
        cases = _clean(_fallback_cases(analysis), analysis.input_width, warnings)
    # Baselines belong inside the limit, and reviewed cases cannot be displaced. A subprogram's
    # branch/threshold cases come first so its coverage never depends on the model.
    cases = _clean(anchors + _baseline(analysis) + driver_cases + cases, analysis.input_width, warnings)[:MAX_CASES]
    if os.getenv("LLM_MODE", "real").lower() == "real" and len(cases) < MIN_CASES:
        raise ValueError(f"Only {len(cases)} distinct inputs; require {MIN_CASES}-{MAX_CASES}")

    for w in warnings:
        print(f"[generate_inputs] {w}", file=sys.stderr)
    LAST_RUN.clear()
    LAST_RUN.update(cases=cases, warnings=warnings)
    return [c["input"] for c in cases]
