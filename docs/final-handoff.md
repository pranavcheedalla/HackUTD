# Person 2 final handoff: segments 1–12

## Delivered

| Module | Original | Inputs | Golden reference | Source lines |
| --- | --- | --- | --- | --- |
| interest | legacy/interest.cbl | legacy/inputs/interest.json | golden/interest.jsonl | 99 |
| payroll | legacy/payroll.cbl | legacy/inputs/payroll.json | golden/payroll.jsonl | 104 |
| invoice | legacy/invoice.cbl | legacy/inputs/invoice.json | golden/invoice.jsonl | 101 |

Each module has 15 handwritten input strings, including ordinary, zero,
negative, and maximum-field cases. Each recording contains exactly 15 actual
COBOL input/output pairs: 45 committed golden cases total. Hello-world lives
under examples/ so discovery under legacy/ finds only the three demo originals.

All five named shared-contract functions are implemented without signature
changes. The task's phrase “six functions” counted five names:

```python
legacy.compile_cobol(cobol_path) -> binary_path
legacy.run_cobol(binary_path, input_line: str) -> str
legacy.record_golden(module_id, binary_path, inputs: list[str]) -> golden_path
testing.golden_to_pytest(module_id, py_module_path) -> test_path
testing.run_equivalence(module_id) -> {passed, total, failures}
```

Tests use real subprocesses for COBOL and pytest. Runtime checks cover exact
stdout, trailing-newline handling, independent stderr, timeouts, child cleanup,
compile failures, source-name collisions, locale, golden integrity, and atomic
recording. The runner checks collection failures, incomplete/skipped runs,
source reload, exceptions, and stale generated tests. Separate Decimal audits
cover 132 interest, 165 payroll, and 235 invoice examples (532 total).

## Run the handoff on macOS

From the repository root:

```bash
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install gnucobol python@3.11
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python check_setup.py
python record_interest.py --check
python record_payroll.py --check
python record_invoice.py --check
python -m pytest -q
python check_integration.py --output runs/person2-smoke.json
```

The smoke command re-records originals into a temporary directory, verifies
those against committed references, generates pytest files, and runs the
handwritten audit fixtures. It passes 45/45 cases, changes invoice to rounding
and catches two failures, then restores truncation and passes invoice 15/15.
The saved references, modern/ directory, and team runs/state.json are untouched.
This command is a standalone process; it temporarily configures private module
paths and restores them even on failure. The default prints JSON; --output also
saves that report atomically. Do not call it concurrently in a shared process.

The smoke is explicitly labeled `person2_contract_with_handwritten_fixtures`.
It is a deterministic runtime/harness demo, not a Nemotron/LangGraph run.

## Segment 11: integration status

At the integration check, fetched origin/main and origin/Pranav both contained
only the initial README (commit 78ce59a). No team contract.py, agent code,
LangGraph graph, or generated modern modules were available on those refs.

Verified locally: function parameter names, three-original discovery layout,
compile/record/generate/verify calls, exact TestResult shape, and the invoice
failure/repair loop. The actual model/orchestrator integration remains pending
the teammate implementation. This handoff does not claim that unavailable code
has passed. Hemant should run these checks after merging:

1. Discover the three module IDs in dependency order; all have no CALL/COPY deps.
2. Extract specs and generate list[str] inputs using the documented formats.
3. Compile each original and record actual results. Keep path fields from the
   returned values; binaries include source-path hashes.
4. Generate equivalence tests before the rewrite exists; imports occur at test time.
5. Write the model rewrite exposing main(input_line: str) -> str.
6. Run equivalence and copy passed/total/failures into module state. Route ordinary
   failures back to rewrite; infrastructure exceptions should mark an execution
   failure, not success. After retry exhaustion, invoke Person 4's explainer.
7. Exercise invoice with the known rounding mutation and verify the explainer
   labels and explains the actual truncation behavior.

Handwritten fixture checks cannot substitute for steps 2, 5, and 7 with real
agents. Golden matches establish behavior on the chosen inputs, not proof over
all inputs. Test execution is on this Mac; ZIP relocation is not another OS test.

The committed recordings and sample-smoke checks deliberately use the 15
handwritten cases per module. Person 3 can generate a different input set;
record_golden will replace that module's recording as specified by the contract,
and the equivalence runner counts those new records dynamically. Run the live
pipeline in its own checkout/worktree to preserve this baseline for regression
checks. Regenerate tests after changing input sets. The sample smoke's fixed
15-case expectations must not be used to judge a new generated input set.

## Merge guidance and boundaries

Repository: https://github.com/pranavcheedalla/HackUTD
Branch: person2/legacy-runtime-harness
PR: https://github.com/pranavcheedalla/HackUTD/pull/1

Hemant owns the merge. Review the separate runtime, harness, payroll, invoice,
and final-handoff commits. Adapt implementations into the team's stubs if the
layout changes; preserve the public signatures and JSONL/TestResult schemas.
Avoid conflicting legacy.py and legacy/ imports. Merge pytest configuration
rather than replacing another person's configuration. Keep testing_reporter.py
with testing.py. No NVIDIA key or additional model calls are needed to run this
component. Portable archives omit executables, caches, environments, and .git.

Rules and all annotated cases: README.md, docs/payroll.md, docs/invoice.md.
Raw local validation, source/golden hashes, and fresh-archive checks are in the
downloadable archive's validation/ folder. Do not change golden answers to make
a failing rewrite pass; --update is only for reviewed original/input changes.
