# HackUTD

# Person 2: legacy runtime and golden recordings

All Person 2 components are implemented: three COBOL originals with 15 real
golden outputs each, compilation/execution, generated pytest tests, and structured
equivalence results. The final integration smoke demonstrates the truncation
failure and repair. Real model/orchestrator integration awaits teammate code.
No NVIDIA key, model call, teammate agent, or Python rewrite is needed for this batch.

## Quick start on macOS

Run these commands from this package's directory, which contains this README:

```bash
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install gnucobol python@3.11
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python check_setup.py
python record_interest.py
python record_payroll.py --check
python record_invoice.py --check
python -m pytest -q
```

The initial build on the user's Mac was checked with GnuCOBOL 3.2.0,
Python 3.11.15, and pytest 9.2.0. A development virtual environment was created
in the enclosing workspace's `work/.venv`; it is not included in the handoff.
Do not use the Mac's `/usr/bin/python3`, which was Python 3.9.6 at setup.
`requirements-dev.lock` pins the verified versions; `requirements-dev.txt`
provides a broader pytest version range if the team manages its own lockfile.

The repeatable setup smoke test uses `examples/hello.cbl`, outside `legacy/`,
so the understanding agent sees only the actual demo program. It compiles and prints:

```text
HELLO FROM COBOL
```

Both commands work when invoked by their absolute paths from another directory.
They resolve source and inputs relative to their own locations. `check_setup.py`
requires the agreed Python 3.11 and returns a nonzero status on a setup failure.

`record_interest.py` creates a missing golden file, but **verifies an existing
file without changing it**. A mismatch prints the differing cases and exits 1.
Use `python record_interest.py --check` to require an existing reference, or
`python record_interest.py --update` to deliberately re-record after reviewing
source/input changes. The shared `record_golden` API still records and replaces
atomically as specified; this protection is in the sample command.

## Contents

```text
legacy/
  __init__.py                 # shared imports: import legacy
  runtime.py                 # compile_cobol, run_cobol, record_golden
  interest.cbl               # 99-line original COBOL sample
  payroll.cbl                # 104-line payroll with overtime and progressive tax
  invoice.cbl                # 101-line invoice with PIC decimal truncation
  inputs/interest.json       # 15 handwritten interest input strings
  inputs/payroll.json        # 15 handwritten payroll input strings
  inputs/invoice.json        # 15 handwritten invoice input strings
  bin/                       # generated local executables, gitignored
golden/interest.jsonl         # 15 interest outputs recorded by executing COBOL
golden/payroll.jsonl          # 15 payroll outputs recorded by executing COBOL
golden/invoice.jsonl          # 15 invoice outputs recorded by executing COBOL
tests/runtime/test_runtime.py
examples/hello.cbl             # outside the agent's scanned legacy directory
check_setup.py                 # repeatable Python/compiler/runtime smoke check
record_interest.py             # create/check by default; explicit --update
HANDOFF.md                   # integration instructions for Hemant/P3/P4
PROGRESS.md                  # resume point and deferred segments
validation/                  # verification results and provenance
```

## Interest program's exact behavior

The program reads one line, without prompts, in this format:

```text
principal|annual_rate_percent|years
1000.00|5.00|2
```

| Field | Accepted value | COBOL storage |
| --- | --- | --- |
| Principal | 0 through 99999.99; 1–5 integer digits; optional 1–2 fractional digits | `PIC 9(5)V99` |
| Annual percentage rate | 0 through 100.00; 1–3 integer digits; optional 1–2 fractional digits | `PIC 9(3)V99` |
| Years | 0 through 99; 1–2 integer digits; no decimal point | `PIC 99` |

Exactly two `|` separators are required. ASCII spaces around each field are
accepted. Signs (including `+`), exponent notation, grouping commas, missing
fields, extra fields, and excess digit counts are rejected. Leading zeros are
accepted within each field's digit-count limit. Use input lines of at most
256 characters, the original's ACCEPT buffer width. Inputs longer than that
are outside this sample's supported input contract.

Calculation:

```text
interest = principal × annual_rate_percent × years / 100
```

The result uses `COMPUTE ... ROUNDED` to two decimal places. For these
nonnegative inputs this rounds half a cent upward. Output is `INTEREST=`
followed by exactly seven integer digits, a dot, and two fractional digits:

```text
INTEREST=0000100.00
```

There is no currency symbol, thousands separator, or extra space. COBOL
DISPLAY emits one final newline, removed by `run_cobol` before recording.
This program returns only the interest, not principal plus interest.

Business validation failures print `ERROR:INVALID_INPUT` and exit successfully;
these are legitimate golden outputs. An arithmetic size-error guard prints
`ERROR:OVERFLOW`; it is defensive, since the valid input ranges fit the output.
The largest valid result is `9899999.01`.

## The 15 handwritten cases

| # | Input | Coverage | Recorded output |
| --- | --- | --- | --- |
| 1 | `1000.00\|5.00\|2` | Ordinary calculation | `INTEREST=0000100.00` |
| 2 | `2500.50\|3.75\|3` | Decimal inputs and rounding | `INTEREST=0000281.31` |
| 3 | `100.00\|100.00\|1` | Maximum valid rate | `INTEREST=0000100.00` |
| 4 | `0.00\|5.00\|2` | Zero principal | `INTEREST=0000000.00` |
| 5 | `1000.00\|0.00\|2` | Zero rate | `INTEREST=0000000.00` |
| 6 | `1000.00\|5.00\|0` | Zero years | `INTEREST=0000000.00` |
| 7 | `-100.00\|5.00\|1` | Negative principal | `ERROR:INVALID_INPUT` |
| 8 | `100.00\|-5.00\|1` | Negative rate | `ERROR:INVALID_INPUT` |
| 9 | `100.00\|5.00\|-1` | Negative years | `ERROR:INVALID_INPUT` |
| 10 | `99999.99\|100.00\|99` | All maximum valid values | `INTEREST=9899999.01` |
| 11 | `99999.99\|0.01\|1` | Maximum principal, tiny rate | `INTEREST=0000010.00` |
| 12 | `0.01\|0.01\|1` | Tiny result rounds to zero | `INTEREST=0000000.00` |
| 13 | `1.00\|0.50\|1` | Half-cent rounds upward | `INTEREST=0000000.01` |
| 14 | `100000.00\|5.00\|1` | Principal exceeds field width | `ERROR:INVALID_INPUT` |
| 15 | `100.00\|100.01\|1` | Rate exceeds permitted value | `ERROR:INVALID_INPUT` |

The table documents outputs already obtained from the executable. The recorder
does not use this table, the test expectations, or Python arithmetic to create
golden answers.

## Shared Python API

```python
from pathlib import Path
import json
import legacy

root = Path.cwd()  # when working from this package directory
binary = legacy.compile_cobol(root / "legacy/interest.cbl")
output = legacy.run_cobol(binary, "1000.00|5.00|2")
assert output == "INTEREST=0000100.00"

inputs = json.loads((root / "legacy/inputs/interest.json").read_text())
golden_path = legacy.record_golden("interest", binary, inputs)
```

`compile_cobol` returns an absolute string path. Source paths supplied by a
caller resolve against that caller's working directory. It builds with
`cobc -x -free`, with a 30-second timeout. The executable is staged and then
atomically moved into `legacy/bin/<source_stem>-<source_path_hash>`. The hash
keeps sources with identical basenames in different directories separate.
Always use the returned path; it can differ when the project is relocated.
A compilation failure raises an error; callers must never
fall back to a previous executable after that error.

`run_cobol` starts a fresh process for each case, sends UTF-8 input with one
newline, and uses a 5-second timeout. The supplied string must not contain CR
or LF. It captures stdout and stderr separately and preserves stdout as bytes
until decoding. Exactly one final LF or CRLF is removed; other spaces and line
endings remain untouched. stdout must be UTF-8. Nonzero exits, missing binaries,
timeouts, and invalid output encoding raise `CobolRunError`.
Invalid Python strings are rejected before execution. Compilation and execution
run with locale `C` for consistent numeric handling. This runtime targets
macOS/POSIX: each subprocess starts a new process group, so a timeout terminates
the ordinary child processes as well. Pipe cleanup has a bounded grace period.
This is process management, not a sandbox for hostile executables.

`record_golden` accepts a nonempty list of strings and writes UTF-8 JSONL at
the package root's `golden/<module_id>.jsonl`, irrespective of caller cwd.
It preserves input order, duplicate inputs, spaces, and multiline output via
JSON escaping. The entire input list is validated before any case runs.
Module IDs must match `[A-Za-z_][A-Za-z0-9_]*`. It atomically
replaces an existing recording only after every case succeeds. On any failure,
the temporary file is cleaned up and any old recording stays intact.

Do not regenerate golden files to make a failing Python rewrite pass. The
recording is the original's reference behavior. Regenerate deliberately when
the original source or agreed test inputs change.

## Verification and next batch

Run `python -m pytest -q` from this directory. The runtime tests execute actual
COBOL and subprocess fixtures: all 15 expected sample outcomes, malformed input,
format preservation, stderr separation, compile/run failures, timeout handling,
and atomic recording. They also inspect the shipped golden file. The review
added 132 deterministic arithmetic examples checked with an independent Decimal
oracle, colliding-source-name checks, child-process timeout checks, locale
checks, and reference-drift CLI checks in a relocated directory with spaces.
See `validation/REVIEW.md` for the findings and requirement mapping.

These are runtime checks, not the generated Python-rewrite equivalence tests.
Segments 5–8 below supply `testing.golden_to_pytest` and `testing.run_equivalence`.
Payroll and invoice are complete. The final handoff documents remaining team integration. See `PROGRESS.md` for the resume point.

## Segments 5–8: equivalence harness

The two remaining shared functions are implemented in `testing.py`:

```python
import testing

# Safe before modern/interest.py exists: this writes tests without importing it.
test_path = testing.golden_to_pytest("interest", "modern/interest.py")
# Call only after Person 4 has written the rewrite.
result = testing.run_equivalence("interest")
# {"passed": 15, "total": 15, "failures": []}
```

Paths supplied by callers resolve against their working directory. Rewrites
inside this project are referenced relative to the project in generated tests,
so moving the complete project keeps those tests usable. External paths stay
absolute. Generated files live in `tests/equivalence/` and are ordinary pytest
files, also runnable with `python -m pytest tests/equivalence/test_interest.py`.
No generated test is committed before a real rewrite is available; normal test
runs therefore do not fail because a teammate's rewrite is still missing.

Tests embed the validated golden cases and their SHA-256. If the golden file
changes, `run_equivalence` refuses to run until tests are regenerated. One case
is generated per record, including duplicates. Whitespace, quotes, Unicode,
empty strings, and output newlines are compared exactly.

The runner invokes pytest in a fresh Python subprocess with a private reporting
plugin (`testing_reporter.py`). Case counts and failures come from pytest hooks,
not scraped terminal text. It disables third-party plugin autoload and inherited
pytest options. Rewrite source is compiled directly on import, avoiding stale
bytecode after rapid same-size edits. Sibling imports and dataclasses are
supported. The runner has a 30-second whole-run timeout with process-group cleanup.

Mismatches and rewrite/import exceptions return failed cases. An exception's
`actual` string includes its traceback. Collection failures, missing generated
tests, stale recordings, timeouts, skipped/incomplete runs, and missing reports
raise `EquivalenceError`; they never produce a successful zero-test result.
The return dictionary has exactly `passed`, `total`, and `failures`, each failure
containing `input`, `expected`, and `actual`. Non-string results fail the test.

The additional harness tests run in temporary projects. A handwritten Decimal
fixture passes all 15 actual interest golden cases, independently of Person 4's
agent. It is a test fixture, not the team's generated Python rewrite.


## Segment 9: payroll

The second original is `legacy/payroll.cbl`, with 15 inputs in
`legacy/inputs/payroll.json` and real outputs in `golden/payroll.jsonl`.
It implements 40-hour regular pay, 1.5x overtime, and fictional progressive
weekly tax brackets at $500 and $1,000. All arithmetic and formatting details,
15 annotated cases, and teammate integration examples are in
[the payroll handoff](docs/payroll.md).

```bash
python record_payroll.py --check
python -m pytest -q tests/runtime/test_payroll.py
```

The interest sample and all five shared function signatures are unchanged.


## Invoice and final integration handoff

The third original is `legacy/invoice.cbl` with 15 inputs and actual outputs.
Its `PIC 9(5)V99` silently truncates fractional cents. For `1|12.35|0.01`,
COBOL returns `TOTAL=00012.34`; a rounding rewrite incorrectly returns
`TOTAL=00012.35`. [Invoice rules and cases](docs/invoice.md).

```bash
python record_invoice.py --check
python check_integration.py --output runs/person2-smoke.json
```

The smoke verifies all 45 cases using handwritten fixtures, catches the invoice
rounding mutation, and verifies the repair. It uses temporary recordings and
tests, preserving committed references and team state. It does not run models
or LangGraph. [Final handoff and integration checklist](docs/final-handoff.md).
