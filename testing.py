"""
P2 — Test harness. STUB VERSION until P2's real code is merged.

Convention: the rewritten module lives at modern/<module_id>.py and exposes
    def main(input_line: str) -> str
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLDEN_DIR = ROOT / "golden"
MODERN_DIR = ROOT / "modern"
EQ_DIR = ROOT / "tests" / "equivalence"

STUB = True


def golden_to_pytest(module_id: str, py_module_path: str) -> str:
    """Generate tests/equivalence/test_<module_id>.py asserting exact output per golden case."""
    EQ_DIR.mkdir(parents=True, exist_ok=True)
    test_path = EQ_DIR / f"test_{module_id}.py"
    test_path.write_text(f'''import json, importlib.util, pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("{module_id}", ROOT / "modern" / "{module_id}.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
CASES = [json.loads(l) for l in (ROOT / "golden" / "{module_id}.jsonl").read_text().splitlines() if l.strip()]

@pytest.mark.parametrize("case", CASES, ids=[str(i) for i in range(len(CASES))])
def test_equivalence(case):
    assert mod.main(case["input"]) == case["output"]
''')
    return str(test_path)


def run_equivalence(module_id: str) -> dict:
    """Return {passed, total, failures:[{input, expected, actual}]}."""
    cases = [json.loads(l) for l in (GOLDEN_DIR / f"{module_id}.jsonl").read_text().splitlines() if l.strip()]
    py_path = MODERN_DIR / f"{module_id}.py"
    spec = importlib.util.spec_from_file_location(f"modern_{module_id}", py_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    failures = []
    for c in cases:
        try:
            actual = mod.main(c["input"])
        except Exception as e:
            actual = f"<exception: {type(e).__name__}: {e}>"
        if actual != c["output"]:
            failures.append({"input": c["input"], "expected": c["output"], "actual": actual})
    return {"passed": len(cases) - len(failures), "total": len(cases), "failures": failures}
