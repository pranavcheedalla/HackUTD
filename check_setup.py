"""One-command, repeatable compiler/runtime smoke check for a teammate's Mac."""

from pathlib import Path
import subprocess
import sys

from legacy import LegacyError, compile_cobol, run_cobol


def main() -> int:
    if sys.version_info[:2] != (3, 11):
        print("Setup requires Python 3.11; run this with python3.11.", file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parent
    try:
        binary = compile_cobol(root / "examples/hello.cbl")
        output = run_cobol(binary, "")
        if output != "HELLO FROM COBOL":
            raise LegacyError(f"Unexpected hello-world output: {output!r}")
        version = subprocess.run(
            ["cobc", "--version"], capture_output=True, check=True, timeout=5,
        ).stdout.decode().splitlines()[0]
    except (LegacyError, OSError, subprocess.SubprocessError) as exc:
        print(f"Setup check failed: {exc}", file=sys.stderr)
        return 1
    print(f"Python {sys.version.split()[0]}; {version}")
    print(output)
    print("PASS: compiler and original executable work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
