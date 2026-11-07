# First sample handoff

## Status and integration boundary

The supplied workspace was empty and was not a Git repository. There was no
team `contract.py` or existing stub to replace. This package uses the supplied shared function names and is now published on
the Person 2 branch in HackUTD, with PR #1 open. It has not been merged.
Hemant remains the integration owner. Do not treat this as a completed team
pipeline or Python rewrite.

Delivered entry points:

```python
legacy.compile_cobol(cobol_path) -> str
legacy.run_cobol(binary_path, input_line: str) -> str
legacy.record_golden(module_id, binary_path, inputs: list[str]) -> str
```

The `legacy` folder is a Python package and also holds the original `.cbl` files,
as allowed by the agreed layout. If the team has already chosen another
implementation location, copy the implementations into its existing stubs
without changing these public signatures. Do not create both `legacy.py` and a
competing `legacy/` package. Merge pytest configuration into the team's existing
configuration rather than replacing it. `testpaths` is `tests`, so future
`tests/equivalence/` and other team tests will also be discovered.

## For Hemant / Person 1

1. Merge source, input JSON, golden JSONL, tests, and applicable documentation.
2. Install GnuCOBOL on the integration machine. Mac binaries are not portable.
3. Compile locally using `legacy.compile_cobol` before calling the recorder.
   Use the returned binary path: filenames include a source-path hash to avoid
   collisions between modules with identical basenames.
4. Call the recorder with module ID `interest` and a list of input strings.
5. Store its returned absolute golden path in module state.
6. Propagate compile/run errors as pipeline failures; don't turn them into
   successful business outputs or swallow them.

The sample command `record_interest.py --check` detects drift without replacing
the reference. A deliberate update uses `--update`. `check_setup.py` repeats
the hello-world setup check on the integration machine. Runtime timeouts clean
up POSIX process groups, including ordinary compiler/runtime descendants.

Person 2's test generator/runner is included in the second commit. The shared
pipeline orders test generation before rewriting: the generator must create
test source without importing a not-yet-created rewrite. Imports happen when
the generated tests execute.

## For Person 3

- Read `legacy/interest.cbl` for understanding/spec extraction.
- Use module ID `interest`; its dependency list is empty (no CALL or COPY).
- `legacy/inputs/interest.json` provides 15 inputs before your generator works.
- Additional generated cases must follow the documented format and field widths.
- Note that `ROUNDED` is present for interest. The invoice truncation sample is
  intentionally deferred to its later segment.

## For Person 4

- Your Python module must expose `main(input_line: str) -> str`.
- Return the result string; printing it is not the entry-point contract.
- Match `INTEREST=0000100.00` including the seven integer digits.
- Match validation responses and accepted field syntax too.
- Use `decimal.Decimal`; interest's half-cent behavior is positive half-up.
- Don't include the COBOL DISPLAY newline in the returned string.
- The actual reference outputs are `golden/interest.jsonl`.

## Scope remaining

The two equivalence functions are now delivered in the second commit.
Model calls, orchestration, UI, and the final Git merge remain
outside this delivery. Generated tests are created when the pipeline runs.

## Update: segments 5–8 delivered

`testing.py` now supplies `golden_to_pytest` and `run_equivalence` with unchanged
shared signatures. Include `testing_reporter.py` when merging. Generate tests
before rewriting; run them after the Python file exists. Keep the returned
failure list intact for Person 4's repair prompt. A missing rewrite is reported
as failed cases; collection/infrastructure errors raise `EquivalenceError`.

Repository: https://github.com/pranavcheedalla/HackUTD
Branch: person2/legacy-runtime-harness
PR: https://github.com/pranavcheedalla/HackUTD/pull/1
The initial runtime/sample delivery is a separate commit. Hemant owns merging.
The historical scope/status notes above describe the first handoff; this update
adds the equivalence harness. Payroll and invoice are delivered; the final handoff records remaining team integration.


## Segment 9: payroll delivered

Use module ID `payroll`; it has no CALL/COPY dependencies.
Read [docs/payroll.md](docs/payroll.md) for exact input syntax, progressive
tax rules, rounding order, output padding, cases, and pipeline examples.
`record_payroll.py --check` verifies its reference. The actual model rewrite
will go in `modern/payroll.py`; the handwritten file under tests/fixtures/
is only an audit fixture. All five shared functions work unchanged.


## Final update: invoice and handoff ready

All three originals, 45 golden cases, and five shared functions are delivered.
See [the final handoff](docs/final-handoff.md) for setup, merge guidance, and
the actual integration boundary. Run `python check_integration.py` for a
Person 2-only fixture smoke including the invoice divergence and repair.
Real Nemotron/LangGraph integration could not be exercised: fetched main and
Pranav refs contained only the initial README. Hemant owns the final merge.


## Audit update

The latest audit exercised Hemant's actual graph at ee58f2f with fixture agents.
See docs/ACCEPTANCE_CHECKLIST.md and docs/ADVERSARIAL_REVIEW.md. Remove his
legacy.py stub and relocate HELLO.cbl when adopting our package. Generated
tests now include an integrity manifest and should be regenerated once. Live
model calls and real agent behavior remain pending.


## P1 + P2 combined

Hemant's pipeline branch is combined here, including contract, LLM wrapper, graph,
CLI, and state writer. All namespace and file conflicts are resolved. Use the
root README and docs/combined-integration.md. The offline CLI verifies all 45
cases, including invoice repair; real mode refuses remaining agent stubs.
