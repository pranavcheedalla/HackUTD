"""Person 2 integration smoke with handwritten fixtures; no model/pipeline calls."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

import legacy
from legacy import runtime
import testing

ROOT = Path(__file__).resolve().parent
MODULE_IDS = ("interest", "payroll", "invoice")


def run_smoke() -> dict:
    originals = (runtime.GOLDEN_DIR, testing.GOLDEN_DIR, testing.TEST_DIR, testing.REPORT_DIR)
    report = {"mode": "person2_contract_with_handwritten_fixtures", "modules": []}
    try:
        with tempfile.TemporaryDirectory(prefix="person2-smoke-") as folder:
            scratch = Path(folder)
            runtime.GOLDEN_DIR = testing.GOLDEN_DIR = scratch / "golden"
            testing.TEST_DIR = scratch / "tests/equivalence"
            testing.REPORT_DIR = scratch / "reports"
            modern = scratch / "modern"
            modern.mkdir()
            for module_id in MODULE_IDS:
                inputs = json.loads((ROOT / f"legacy/inputs/{module_id}.json").read_text())
                if len(inputs) != 15:
                    raise ValueError(f"Expected 15 inputs: {module_id}")
                binary = legacy.compile_cobol(ROOT / f"legacy/{module_id}.cbl")
                recorded = Path(legacy.record_golden(module_id, binary, inputs))
                saved = ROOT / f"golden/{module_id}.jsonl"
                if recorded.read_bytes() != saved.read_bytes():
                    raise ValueError(f"Original/golden drift for {module_id}; saved reference preserved")
                target = modern / f"{module_id}.py"
                target.write_bytes((ROOT / f"tests/fixtures/{module_id}_reference.py").read_bytes())
                testing.golden_to_pytest(module_id, target)
                result = testing.run_equivalence(module_id)
                if result != {"passed": 15, "total": 15, "failures": []}:
                    raise ValueError(f"Fixture mismatch for {module_id}: {result}")
                report["modules"].append({"module_id": module_id, **result})

            invoice = modern / "invoice.py"
            correct = invoice.read_text()
            invoice.write_text(correct.replace("ROUND_DOWN", "ROUND_HALF_UP"))
            divergence = testing.run_equivalence("invoice")
            canonical = {"input": "1|12.35|0.01", "expected": "TOTAL=00012.34",
                         "actual": "TOTAL=00012.35"}
            if divergence["passed"] != 13 or canonical not in divergence["failures"]:
                raise ValueError(f"Rounding mutation was not caught as expected: {divergence}")
            report["invoice_rounding_mutation"] = divergence
            invoice.write_text(correct)
            repaired = testing.run_equivalence("invoice")
            if repaired != {"passed": 15, "total": 15, "failures": []}:
                raise ValueError(f"Restored truncation did not pass: {repaired}")
            report["invoice_after_restoring_truncation"] = repaired
    finally:
        runtime.GOLDEN_DIR, testing.GOLDEN_DIR, testing.TEST_DIR, testing.REPORT_DIR = originals
    report.update(status="passed", passed=45, total=45,
                  team_pipeline="This smoke does not exercise team agents or graph; see the optional team-graph fixture report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="also save the structured report to this path")
    args = parser.parse_args()
    try:
        result = run_smoke()
        payload = json.dumps(result, indent=2) + "\n"
        if args.output:
            destination = args.output.expanduser().resolve()
            try:
                relative = destination.relative_to(ROOT)
            except ValueError:
                relative = None
            if relative is not None and (not relative.parts or relative.parts[0] not in ('runs', 'validation')):
                raise ValueError('--output inside the project must be under runs/ or validation/')
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent,
                                                 delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(payload)
                os.replace(temporary, destination)
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
        print(payload, end="")
        return 0
    except (legacy.LegacyError, testing.EquivalenceError, OSError, ValueError) as exc:
        print(f"Person 2 integration smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
