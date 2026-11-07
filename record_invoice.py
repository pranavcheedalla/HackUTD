"""Record the original invoice sample, or verify saved outputs without replacing them."""

import argparse
import json
from pathlib import Path
import sys

from legacy import LegacyError, compile_cobol, record_golden, run_cobol


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="require and verify a golden file")
    mode.add_argument("--update", action="store_true", help="explicitly replace golden outputs")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    destination = root / "golden/invoice.jsonl"
    try:
        inputs = json.loads((root / "legacy/inputs/invoice.json").read_text(encoding="utf-8"))
        if not isinstance(inputs, list) or len(inputs) != 15 or not all(
            isinstance(item, str) for item in inputs
        ):
            raise ValueError("Invoice sample requires exactly 15 string inputs")
        if args.check and not destination.is_file():
            raise ValueError("Golden file is missing; record it before using --check")
        binary = compile_cobol(root / "legacy/invoice.cbl")
        if args.update or not destination.exists():
            golden = record_golden("invoice", binary, inputs)
            print(f"Recorded {len(inputs)} actual COBOL outputs: {golden}")
        else:
            saved = [json.loads(line) for line in destination.read_bytes().splitlines()]
            actual = [{"input": line, "output": run_cobol(binary, line)} for line in inputs]
            if saved != actual:
                print("FAIL: original outputs or inputs differ from the saved golden file.", file=sys.stderr)
                for index in range(max(len(saved), len(actual))):
                    expected = saved[index] if index < len(saved) else None
                    observed = actual[index] if index < len(actual) else None
                    if expected != observed:
                        print(f"Case {index + 1}: saved={expected!r}; actual={observed!r}", file=sys.stderr)
                print("Reference preserved. Review changes before using --update.", file=sys.stderr)
                return 1
            print(f"PASS: all {len(inputs)} original outputs match; golden file preserved.")
        print(f"Compiled: {binary}")
    except (LegacyError, OSError, ValueError, TypeError) as exc:
        print(f"Invoice recording/check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
