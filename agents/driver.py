"""Test driver for CALLed subprograms (owner: P3). Contract: contract.py "CODEBASE SUPPORT".

    make_driver(subprogram_src) -> free-format COBOL source of DRV-<PROGRAM-ID>

A subprogram has no ACCEPT of its own, so it cannot be recorded with the one-line-in /
one-line-out convention. The driver gives it one:

    input   "G|100.00|0"                         one "|" token per USING param, in order
    output  "LK-TIER=G|LK-SUBTOTAL=0000100.00|LK-RATE=12.50"   every param after the CALL

Numeric tokens go through FUNCTION NUMVAL (empty -> 0); text tokens are MOVEd (empty -> spaces).
Reference: tests/fixtures/codebase/drivers/discount_driver.cbl
"""
from __future__ import annotations

import re

from agents.cobol_static import NAME, analyze, edited_pic, kw, strip_comments, using_names

TOKEN_LEN = 64
LINE_LEN = 256


def _call_name(src: str) -> str:
    """PROGRAM-ID as written (CALL literals are case-sensitive entry names)."""
    m = re.search(r"PROGRAM-ID\s*\.\s*(['\"]?)(" + NAME + r")\1", strip_comments(src), re.I)
    if not m:
        raise ValueError("make_driver: no PROGRAM-ID found in the subprogram source")
    return m.group(2)


def _storage_pic(field, param: dict) -> str:
    """PIC (+ USAGE) for the driver's copy of a param, so BY REFERENCE storage matches exactly."""
    if field.pic is None:  # group item: pass a same-length text buffer
        return f"PIC X({param['length']})"
    usage = f" {field.usage}" if field.usage != "DISPLAY" else ""
    sign = " SIGN SEPARATE" if field.sign_separate else ""
    return f"PIC {field.pic}{usage}{sign}"


def make_driver(subprogram_src: str) -> str:
    if not re.search(kw("PROCEDURE") + r"\s+DIVISION\s+USING", strip_comments(subprogram_src), re.I):
        raise ValueError("make_driver: source has no PROCEDURE DIVISION USING; "
                         "it is a main program and needs no test driver")
    names = using_names(subprogram_src)
    analysis = analyze(subprogram_src)
    missing = [n for n in names if n not in analysis.index]
    if not names or missing:
        raise ValueError(f"make_driver: USING parameters not declared in LINKAGE SECTION: {missing or names}")
    params = analysis.params
    pid = _call_name(subprogram_src)
    n = len(params)

    line_len = max(LINE_LEN, sum(max(TOKEN_LEN, p["length"]) for p in params) + n)
    ws = [f"01 IN-LINE PIC X({line_len})."]
    ws += [f"01 T{i} PIC X({max(TOKEN_LEN, p['length'])})." for i, p in enumerate(params, 1)]
    ws += [f"01 P{i} {_storage_pic(analysis.index[p['name']], p)}." for i, p in enumerate(params, 1)]
    ws += [f"01 E{i} PIC {edited_pic(p)}." for i, p in enumerate(params, 1) if p["kind"] == "numeric"]

    proc = ["    ACCEPT IN-LINE",
            '    UNSTRING IN-LINE DELIMITED BY "|"',
            "        INTO " + " ".join(f"T{i}" for i in range(1, n + 1))]
    for i, p in enumerate(params, 1):
        proc.append(f"    COMPUTE P{i} = FUNCTION NUMVAL(T{i})" if p["kind"] == "numeric" else f"    MOVE T{i} TO P{i}")
    proc.append(f"    CALL '{pid}' USING " + " ".join(f"P{i}" for i in range(1, n + 1)))
    proc += [f"    MOVE P{i} TO E{i}" for i, p in enumerate(params, 1) if p["kind"] == "numeric"]
    shown = []
    for i, p in enumerate(params, 1):
        label = ("" if i == 1 else "|") + f"{p['name']}="
        shown += [f'"{label}"', f"E{i}" if p["kind"] == "numeric" else f"P{i}"]
    proc.append("    DISPLAY " + shown[0])
    proc += [f"        {item}" for item in shown[1:]]  # one operand per line: no long source lines
    proc.append("    STOP RUN.")

    return "\n".join([
        "IDENTIFICATION DIVISION.",
        f"PROGRAM-ID. DRV-{pid.upper()}.",
        f"*> Generated test driver for {pid} (agents/driver.py). Input: one '|' token per param.",
        "DATA DIVISION.",
        "WORKING-STORAGE SECTION.",
        *ws,
        "PROCEDURE DIVISION.",
        *proc,
        "",
    ])
