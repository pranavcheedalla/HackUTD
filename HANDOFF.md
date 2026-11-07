# First sample handoff

## Status and integration boundary

The supplied workspace was empty and was not a Git repository. There was no
team `contract.py` or existing stub to replace. This is a standalone package
using the supplied shared function names; it has not been pushed or merged.
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

Person 2's test generator/runner will arrive in the next batch. The shared
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

Not included in this first handoff: generated equivalence tests, the
`testing` module, model calls, orchestration, payroll, invoice, UI, or Git merge.
Only segments 1–4 were requested for this batch.
