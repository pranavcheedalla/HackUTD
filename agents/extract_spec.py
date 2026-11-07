"""Phase 2 - Spec. Nemotron Nano reads COBOL and returns the Spec JSON.

    extract_spec(cobol_src) -> Spec
    Spec = {module_id, summary, inputs:[{name,type,format}], outputs:[{name,type,format}],
            business_rules:[str], edge_cases:[str], quirks:[str]}

Pass the source with copybooks expanded (agents.understand.load_cobol_source) so the
model can see every field. module_id is the PROGRAM-ID lowercased; the pipeline should
overwrite it with the module_id from understand().
"""
from __future__ import annotations

import json
import re
import sys

from agents import _llm
from agents._json import extract_json
from agents.cobol_static import analyze, numbered, render_summary

MODEL = "nano"

# ----------------------------------------------------------------------------- PROMPTS
EXTRACT_SPEC_SYSTEM = """\
You are a senior COBOL analyst documenting a legacy program before it is rewritten in Python.
A rewrite will only be accepted if it reproduces the COBOL's output byte for byte, so your
spec must capture exact data formats and every behaviour a modern programmer would not expect.

COBOL facts to apply:
- PIC 9 = digit, S = signed, V = IMPLIED decimal point (no '.' is stored or typed in input),
  X = any character, A = letter. 9(5)V99 = 5 integer digits + 2 decimals, 7 characters wide.
- Edited PICs (Z, *, $, comma, '.', +, -, CR, DB, B, 0, /) format numbers for DISPLAY:
  Z replaces leading zeros with spaces; '.' is a real decimal point; '-' shows a sign only
  when negative. The edited PIC fixes the exact width of the output.
- COMPUTE / MULTIPLY / DIVIDE / ADD / SUBTRACT without ROUNDED TRUNCATE extra decimal
  digits (12.349 -> 12.34). With ROUNDED they round half away from zero (12.345 -> 12.35).
- Without ON SIZE ERROR, a result too large for the receiving field silently loses its
  leftmost digits (PIC 9(3): 1234 -> 234).
- An unsigned field (no S) stores the absolute value: a negative result loses its sign.
- ACCEPT reads one line into the receiving field; a group field is filled left to right by
  column position (fixed width). A short line is padded with spaces.
- DISPLAY concatenates its operands with no separators; literal text keeps its exact spacing.

How to fill each key:
- summary: 2-3 plain-English sentences a business person understands.
- inputs: one entry per field of the input line, IN COLUMN ORDER. type = "decimal",
  "integer" or "string". format = exact columns + PIC + meaning, e.g.
  "cols 1-9, PIC 9(7)V99, 9 digits with 2 implied decimals, no decimal point, zero-padded".
- outputs: one entry per DISPLAY line, in the order printed. format = the exact layout:
  literal text with its spacing, the edited PIC, and the total width.
- business_rules: each calculation and decision as a precise rule with the formula,
  e.g. "discount = subtotal * rate / 100, truncated to 2 decimals".
- edge_cases: concrete inputs that hit boundaries or special paths, with what happens.
- quirks: EVERY truncation, missing ROUNDED, overflow without ON SIZE ERROR, sign loss,
  implied decimal, space-in-numeric-field or fixed-width behaviour. Name the field and its
  PIC and give a numeric example. If the STATIC ANALYSIS lists a truncation, it MUST be here.
"""

EXTRACT_SPEC_USER = """\
Write the spec for this COBOL program. Use module_id "{module_id}".

STATIC ANALYSIS (computed by a parser - treat these facts as correct):
{static}

COBOL SOURCE (line numbers added):
{source}
"""

EXTRACT_SPEC_RETRY = """\

Your previous answer did not match the required schema:
{errors}

Previous answer:
{previous}

Return the corrected, complete JSON object only.
"""
# -----------------------------------------------------------------------------

_IO_ITEM = {
    "type": "object",
    "required": ["name", "type", "format"],
    "properties": {"name": {"type": "string"}, "type": {"type": "string"}, "format": {"type": "string"}},
}
_STR_LIST = {"type": "array", "items": {"type": "string"}}
SPEC_SCHEMA = {
    "type": "object",
    "required": ["module_id", "summary", "inputs", "outputs", "business_rules", "edge_cases", "quirks"],
    "properties": {
        "module_id": {"type": "string"},
        "summary": {"type": "string"},
        "inputs": {"type": "array", "items": _IO_ITEM},
        "outputs": {"type": "array", "items": _IO_ITEM},
        "business_rules": _STR_LIST,
        "edge_cases": _STR_LIST,
        "quirks": _STR_LIST,
    },
}
_LIST_KEYS = ("business_rules", "edge_cases", "quirks")
_IO_KEYS = ("inputs", "outputs")


def validate_spec(spec) -> list[str]:
    """Return a list of schema problems (empty list = valid)."""
    if not isinstance(spec, dict):
        return [f"top level must be a JSON object, got {type(spec).__name__}"]
    errors = [f"missing key '{k}'" for k in SPEC_SCHEMA["required"] if k not in spec]
    for k in ("module_id", "summary"):
        if k in spec and (not isinstance(spec[k], str) or not spec[k].strip()):
            errors.append(f"'{k}' must be a non-empty string")
    for k in _LIST_KEYS:
        if k in spec and not (isinstance(spec[k], list) and all(isinstance(x, str) for x in spec[k])):
            errors.append(f"'{k}' must be a list of strings")
    for k in _IO_KEYS:
        if k not in spec:
            continue
        if not isinstance(spec[k], list) or not spec[k]:
            errors.append(f"'{k}' must be a non-empty list of {{name, type, format}} objects")
            continue
        for i, item in enumerate(spec[k]):
            if not isinstance(item, dict):
                errors.append(f"'{k}[{i}]' must be an object with name, type, format")
                continue
            for f in ("name", "type", "format"):
                if not isinstance(item.get(f), str) or not item.get(f, "").strip():
                    errors.append(f"'{k}[{i}].{f}' must be a non-empty string")
    return errors


def _light_fix(raw, module_id: str):
    """Fix harmless shape slips before validating (string instead of list, number as string)."""
    if isinstance(raw, str):
        try:
            raw = extract_json(raw)
        except ValueError:
            return raw
    if isinstance(raw, dict) and "spec" in raw and isinstance(raw["spec"], dict) and "summary" not in raw:
        raw = raw["spec"]  # model wrapped it
    if not isinstance(raw, dict):
        return raw
    raw = dict(raw)
    raw["module_id"] = module_id
    for k in _LIST_KEYS:
        v = raw.get(k)
        if isinstance(v, str):
            raw[k] = [v] if v.strip() else []
        elif isinstance(v, list):
            raw[k] = [x if isinstance(x, str) else json.dumps(x) for x in v]
    for k in _IO_KEYS:
        if isinstance(raw.get(k), list):
            raw[k] = [{f: str(i.get(f, "")) for f in ("name", "type", "format")} if isinstance(i, dict) else i
                      for i in raw[k]]
    return raw


def _force_fix(raw, module_id: str, analysis) -> dict:
    """Last resort after the retry also failed: fill gaps so the pipeline can continue."""
    raw = raw if isinstance(raw, dict) else {}
    spec = {"module_id": module_id, "summary": str(raw.get("summary") or f"COBOL program {module_id}.")}
    for k in _IO_KEYS:
        items = [i for i in raw.get(k, []) if isinstance(i, dict)] if isinstance(raw.get(k), list) else []
        spec[k] = [{f: str(i.get(f) or "unknown") for f in ("name", "type", "format")} for i in items]
    if not spec["inputs"] and analysis.input_layout:
        spec["inputs"] = [{"name": f["name"], "type": "decimal" if "decimals" in f["meaning"] else "string",
                           "format": f"cols {f['start']}-{f['end']}, {f['meaning']}"} for f in analysis.input_layout]
    if not spec["outputs"]:
        spec["outputs"] = [{"name": f"line{i}", "type": "string", "format": t}
                           for i, (_, t) in enumerate(analysis.displays, 1)] or [
            {"name": "stdout", "type": "string", "format": "unknown"}]
    for k in _LIST_KEYS:
        v = raw.get(k, [])
        spec[k] = [str(x) for x in v] if isinstance(v, list) else ([str(v)] if v else [])
    return spec


def _add_static_quirks(spec: dict, analysis) -> dict:
    """Safety net: truncations the parser proved must appear in quirks, even if the model missed them."""
    quirks = [q.upper() for q in spec["quirks"]]
    for stmt in analysis.arithmetic:
        for name in stmt.truncation_targets:
            if any(name in q and re.search(r"TRUNC|ROUND", q) for q in quirks):
                continue
            note = next(n for n in stmt.notes if n.startswith(name))
            spec["quirks"].append(f"[static check, line {stmt.line}] {note}")
    return spec


def _call(system: str, user: str, schema: dict):
    """call_llm, but a failed call (timeout, bad JSON, 5xx) becomes "" so the fallbacks run."""
    try:
        return _llm.call_llm(MODEL, system, user, schema)
    except Exception as exc:  # noqa: BLE001 - the pipeline must keep going
        print(f"[{__name__}] LLM call failed, using fallback: {exc!r}"[:300], file=sys.stderr)
        return ""


def extract_spec(cobol_src: str) -> dict:
    analysis = analyze(cobol_src)
    module_id = (analysis.program_id or "module").lower().replace("-", "_")
    user = EXTRACT_SPEC_USER.format(module_id=module_id, static=render_summary(analysis),
                                    source=numbered(cobol_src))

    raw = _call(EXTRACT_SPEC_SYSTEM, user, SPEC_SCHEMA)
    spec = _light_fix(raw, module_id)
    errors = validate_spec(spec)
    if errors:
        print(f"[extract_spec] {module_id}: schema errors, retrying once: {errors}", file=sys.stderr)
        previous = spec if isinstance(spec, str) else json.dumps(spec, indent=1)
        retry_user = user + EXTRACT_SPEC_RETRY.format(errors="\n".join(f"- {e}" for e in errors),
                                                      previous=str(previous)[:6000])
        raw = _call(EXTRACT_SPEC_SYSTEM, retry_user, SPEC_SCHEMA)
        spec = _light_fix(raw, module_id)
        errors = validate_spec(spec)
        if errors:
            print(f"[extract_spec] {module_id}: still invalid after retry {errors}; filling gaps",
                  file=sys.stderr)
            spec = _force_fix(spec, module_id, analysis)
    return _add_static_quirks(spec, analysis)
