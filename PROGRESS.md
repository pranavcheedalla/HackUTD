# Person 2 build progress

This file is the resume checkpoint. Read it before rebuilding completed work.

## Completed: segments 1–4

- [x] Inspected the empty workspace; no Git repo, AGENTS.md, stubs, or contract.py.
- [x] Installed GnuCOBOL and Python 3.11 through Homebrew.
- [x] Created a workspace-local virtual environment and installed pytest.
- [x] Compiled and ran hello-world outside the scanned legacy folder.
- [x] Implemented compile_cobol with diagnostics, timeout, and atomic binary update.
- [x] Implemented run_cobol with timeout, separate stderr, and exact stdout handling.
- [x] Wrote interest.cbl (99 lines) with explicit syntax and range validation.
- [x] Handwrote 15 inputs covering ordinary, zero, negative, max, and rounding cases.
- [x] Implemented record_golden with atomic replacement and JSON escaping.
- [x] Recorded 15 actual outputs to golden/interest.jsonl.
- [x] Checked runtime behavior with real subprocesses and the COBOL executable.
- [x] Added setup instructions, sample behavior, and teammate handoff notes.
- [x] Reviewed batch 1: process-group timeouts, locale, executable checks,
      source-name collisions, and complete input prevalidation.
- [x] Added a portable hello-world setup command and golden-drift verification CLI.
- [x] Audited 132 arithmetic examples against an independent Decimal oracle.
- [x] Expanded pytest discovery to all of tests/ for later integration.
- [x] Added regression checks for relocated paths containing spaces.

Verification details and file hashes are saved under `validation/`.
The portable zip excludes executables, virtual environments, and Python caches.

## Resume here: segments 5–8

1. Implement `testing.golden_to_pytest(module_id, py_module_path) -> test_path`.
2. Implement `testing.run_equivalence(module_id) -> {passed, total, failures}`.
3. Validate with matching, deliberately incorrect, and crashing Python fixtures.
4. Harden reporting, process timeout, collection failure, and repeated rewrite runs.

Keep public signatures unchanged. Reuse this batch's existing recordings.
Test generation must work before the Python rewrite exists. Use structured
pytest reporting, not parsing its terminal summary. A fresh subprocess should
load every updated rewrite. Never interpret zero executed tests as success.

## Later: segments 9–12

- Payroll source + 15 inputs + real golden outputs.
- Invoice source + 15 inputs + real golden outputs + demonstrated truncation mismatch.
- Integration checks with available teammates' code.
- Final fresh run, documentation, and handoff to Hemant.

## Environment on this Mac

- Compiler: `/opt/homebrew/bin/cobc`, reports GnuCOBOL 3.2.0.
- Python: `/opt/homebrew/bin/python3.11`, reports 3.11.15.
- Current development environment: enclosing workspace `work/.venv`.
- pytest: 9.2.0.
- There is no connected team repository or Git branch in this workspace yet.
- No NVIDIA credentials were needed or accessed for segments 1–4.

The usage screenshot was a historical snapshot, not live remaining allowance.
The next usage checkpoint is before starting segments 5–8.
