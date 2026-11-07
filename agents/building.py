"""
P4 — Building agents. STUB VERSION until P4's real code is merged.

The stub rewrite is deliberately WRONG on the first attempt (forgets .strip())
so the retry loop gets exercised, then correct once it sees the failures.
"""
from __future__ import annotations

STUB = True

_BUGGY = '''def main(input_line: str) -> str:
    return "OUT:" + input_line.upper()
'''

_FIXED = '''def main(input_line: str) -> str:
    return "OUT:" + input_line.strip().upper()
'''


def rewrite(spec: dict, cobol_src: str, failures: list | None) -> str:
    return _FIXED if failures else _BUGGY


def write_unit_tests(spec: dict, python_src: str) -> str:
    mid = spec["module_id"]
    return f'''import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("{mid}", ROOT / "modern" / "{mid}.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def test_prefix():
    assert mod.main("a").startswith("OUT:")

def test_empty():
    assert mod.main("") == "OUT:"
'''


def explain_divergence(spec: dict, cobol_src: str, python_src: str, failure: dict) -> dict:
    return {"verdict": "new_code_bug",
            "reason": f"[stub] New code returned {failure['actual']!r} but legacy returned {failure['expected']!r}."}
