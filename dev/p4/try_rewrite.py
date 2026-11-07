"""P4 test script: run the rewrite agent on a COBOL program and diff against expected outputs.

Mirrors the pipeline's rewrite -> verify -> retry loop, but standalone (no LangGraph, no cobc,
no P2 harness). Expected outputs are a golden-format jsonl: {"input": str, "output": str}.

  python dev/p4/try_rewrite.py                       # built-in sample, real Nemotron calls
  python dev/p4/try_rewrite.py --offline             # no API key: uses the hand-written reference
  python dev/p4/try_rewrite.py --cobol legacy/x.cbl --spec specs/x.json --expected golden/x.jsonl
  python dev/p4/try_rewrite.py --attempts 3 --unit-tests --explain
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from agents import explain_divergence, rewrite, write_unit_tests  # noqa: E402

OUT = HERE / "out"


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_cases(py_path: Path, cases: list[dict]) -> dict:
    failures = []
    try:
        mod = load_module(py_path)
    except Exception as e:
        err = f"<import error: {type(e).__name__}: {e}>"
        return {"passed": 0, "total": len(cases),
                "failures": [{"input": c["input"], "expected": c["output"], "actual": err} for c in cases]}
    for c in cases:
        try:
            actual = mod.main(c["input"])
        except Exception as e:
            actual = f"<exception: {type(e).__name__}: {e}>"
        if actual != c["output"]:
            failures.append({"input": c["input"], "expected": c["output"], "actual": actual})
    return {"passed": len(cases) - len(failures), "total": len(cases), "failures": failures}


def print_result(res: dict) -> None:
    print(f"  passed {res['passed']}/{res['total']}")
    for f in res["failures"]:
        print(f"  ✗ input    {f['input']!r}\n    expected {f['expected']!r}\n    actual   {f['actual']!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cobol", default=str(HERE / "p4_interest.cbl"))
    ap.add_argument("--spec", default=str(HERE / "p4_interest.spec.json"))
    ap.add_argument("--expected", default=str(HERE / "p4_interest.expected.jsonl"))
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--offline", action="store_true", help="skip the LLM; use the hand-written reference")
    ap.add_argument("--unit-tests", action="store_true", help="also run write_unit_tests + pytest")
    ap.add_argument("--explain", action="store_true", help="explain the first failure if still failing")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    cobol = Path(args.cobol).read_text()
    cases = [json.loads(l) for l in Path(args.expected).read_text().splitlines() if l.strip()]
    module_id = spec["module_id"]
    py_path = OUT / "modern" / f"{module_id}.py"
    py_path.parent.mkdir(parents=True, exist_ok=True)
    (py_path.parent / "__init__.py").touch()

    failures, res, src = None, None, ""
    for attempt in range(1, args.attempts + 1):
        print(f"\n== attempt {attempt}: rewrite {module_id}" + (" (fixing failures)" if failures else ""))
        if args.offline:
            from agents.rewrite import finalize
            src = finalize((HERE / f"reference_{module_id}.py").read_text())
        else:
            src = rewrite(spec, cobol, failures)
        py_path.write_text(src)
        print(f"  wrote {py_path.relative_to(ROOT)} ({len(src.splitlines())} lines)")
        res = run_cases(py_path, cases)
        print_result(res)
        if not res["failures"]:
            print("\n✅ equivalent on all cases")
            break
        failures = res["failures"]
        if args.offline:
            break

    if res["failures"] and args.explain:
        f = res["failures"][0]
        print("\n== explain_divergence on first failure")
        print(" ", json.dumps(explain_divergence(spec, cobol, src, f), indent=2))

    if args.unit_tests and not args.offline:
        print("\n== write_unit_tests")
        test_src = write_unit_tests(spec, src)
        test_path = OUT / "tests" / f"test_{module_id}.py"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(test_src)
        print(f"  wrote {test_path.relative_to(ROOT)}")
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(test_path), "--rootdir", str(OUT)],
                           cwd=OUT, capture_output=True, text=True, env={**__import__("os").environ, "PYTHONPATH": str(OUT)})
        print(r.stdout[-2000:] or r.stderr[-2000:])

    return 0 if not res["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
