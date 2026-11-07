"""P4 · Divergence explainer: one failing case -> {verdict, reason}.

Contract: explain_divergence(spec, cobol_src, python_src, failure) -> {verdict, reason}
  verdict: "new_code_bug"  — the Python is simply wrong (logic, formatting, parsing)
           "legacy_quirk"  — the COBOL does something surprising (truncation, overflow,
                             rounding, sign loss) that a faithful rewrite must copy
  reason:  ONE plain-English sentence a business person understands.

A deterministic diff analysis runs first and is handed to the model as evidence; if the
model call fails, that analysis alone produces the answer, so this never crashes the pipeline.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from agents import _llm

VERDICTS = ("new_code_bug", "legacy_quirk")

EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
}

# ----------------------------------------------------------------------------- prompts
EXPLAIN_SYSTEM = """You audit a COBOL-to-Python migration. For one input, the real COBOL
program printed EXPECTED and the new Python printed ACTUAL. Decide why they differ.

verdict = "legacy_quirk" when the COBOL output comes from surprising legacy data behavior
that a naive rewrite would not copy, for example:
  - fixed-decimal fields (PIC ...V99) TRUNCATE extra decimals instead of rounding
  - a result too big for its PIC field silently loses its leading digits (overflow)
  - an unsigned field drops the minus sign
  - ROUNDED vs not-ROUNDED differences
verdict = "new_code_bug" when the Python is simply wrong: wrong formula or branch,
wrong padding/width/leading zeros, wrong input parsing, crash, missing text.

reason: exactly ONE sentence, under 30 words, for a business person. Use dollar amounts
or numbers from the case. No jargon like PIC, COMP-3 or Decimal. Example:
"The old system cuts off fractions of a cent instead of rounding, so it reports $287.77
where the new code reported $287.78."
"""

EXPLAIN_USER = """## Failing case
input:    {input!r}
expected: {expected!r}   (real COBOL output)
actual:   {actual!r}   (new Python output)

## Automatic diff analysis
{analysis}

## Spec quirks already noted
{quirks}

## COBOL
```cobol
{cobol}
```

## Python
```python
{python}
```"""


# ----------------------------------------------------------------------------- agent
def explain_divergence(spec: dict, cobol_src: str, python_src: str, failure: dict) -> dict:
    analysis = analyze_diff(str(failure.get("expected", "")), str(failure.get("actual", "")))
    user = EXPLAIN_USER.format(
        input=failure.get("input"),
        expected=failure.get("expected"),
        actual=failure.get("actual"),
        analysis="\n".join(f"- {n}" for n in analysis["notes"]) or "- (no numeric pattern found)",
        quirks="\n".join(f"- {q}" for q in (spec or {}).get("quirks", [])) or "- none",
        cobol=cobol_src,
        python=python_src,
    )
    try:
        out = _llm.call_llm("nano", EXPLAIN_SYSTEM, user, EXPLAIN_SCHEMA)
        if isinstance(out, str):
            out = _llm.extract_json(out)
        verdict = str(out.get("verdict", "")).strip().lower().replace(" ", "_")
        reason = _one_sentence(str(out.get("reason", "")))
        if verdict not in VERDICTS or not reason:
            raise ValueError(f"bad explainer output: {out!r}")
        return {"verdict": verdict, "reason": reason}
    except Exception as e:  # never break the pipeline over an explanation
        print(f"[explainer] falling back to heuristic: {e}")
        return {"verdict": analysis["verdict"], "reason": analysis["reason"]}


# ----------------------------------------------------------------------------- diff analysis
_NUM = re.compile(r"-?[\d,]*\d(?:\.\d+)?-?")


def _to_dec(tok: str) -> Decimal | None:
    t = tok.replace(",", "")
    neg = t.endswith("-") or t.startswith("-")
    t = t.strip("-")
    try:
        d = Decimal(t)
    except InvalidOperation:
        return None
    return -d if neg else d


def analyze_diff(expected: str, actual: str) -> dict:
    """Pure-Python evidence: which numbers differ and how. Also yields a fallback verdict."""
    notes: list[str] = []
    verdict, reason = "new_code_bug", "The new code prints something different from the old system for this input."

    if expected.strip() == actual.strip() and expected != actual:
        notes.append("Only whitespace differs (padding/alignment).")
        return {"notes": notes, "verdict": verdict,
                "reason": "The numbers match, but the new code lines the output up differently from the old system."}
    if len(expected) != len(actual):
        notes.append(f"Length differs: expected {len(expected)} chars, actual {len(actual)} chars.")

    exp_nums = [(t, _to_dec(t)) for t in _NUM.findall(expected)]
    act_nums = [(t, _to_dec(t)) for t in _NUM.findall(actual)]
    if len(exp_nums) != len(act_nums):
        notes.append(f"Different count of numbers: expected {len(exp_nums)}, actual {len(act_nums)}.")
        return {"notes": notes, "verdict": verdict, "reason": reason}

    for (et, e), (at, a) in zip(exp_nums, act_nums):
        if e is None or a is None or e == a:
            if et != at:
                notes.append(f"Same value, different formatting: {et!r} vs {at!r}.")
            continue
        delta = a - e
        places = max(-e.as_tuple().exponent, 0)
        ulp = Decimal(1).scaleb(-places) if places else Decimal(1)
        notes.append(f"{et} (COBOL) vs {at} (Python): difference {delta}.")
        if abs(delta) == ulp and places:
            notes.append(
                f"Off by exactly one in the last decimal place: classic truncate-vs-round "
                f"(COBOL drops extra decimals without rounding)."
            )
            verdict = "legacy_quirk"
            reason = (f"The old system cuts off extra fractions of a cent instead of rounding, so it "
                      f"shows {e} where the new code shows {a}.")
        elif e != 0 and abs(a) > abs(e) and _lost_high_digits(e, a):
            notes.append("COBOL value equals the Python value with its leading digits chopped off: field overflow.")
            verdict = "legacy_quirk"
            reason = (f"The result is too large for the old system's number field, so it silently drops the "
                      f"leading digits and shows {e} instead of {a}.")
        elif e == -a:
            notes.append("Same magnitude, opposite sign: an unsigned COBOL field drops the minus sign.")
            verdict = "legacy_quirk"
            reason = f"The old system cannot store negative numbers in this field, so it shows {e} instead of {a}."
    return {"notes": notes, "verdict": verdict, "reason": reason}


def _lost_high_digits(e: Decimal, a: Decimal) -> bool:
    ae, aa = abs(e), abs(a)
    for k in range(1, 15):
        if aa % (Decimal(10) ** k) == ae:
            return True
    return False


def _one_sentence(text: str) -> str:
    text = " ".join(text.split())
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    s = m.group(1) if m else text
    return s if s.endswith((".", "!", "?")) or not s else s + "."
