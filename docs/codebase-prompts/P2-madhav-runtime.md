# Prompt for Madhav (P2): COBOL runtime, compile and link a codebase

> Paste everything below this line into your AI coding assistant (Claude Code / Codex),
> opened in your HackUTD checkout.

---

You are working on **HackUTD "Legacy → Verified"**. It's a hackathon project: NVIDIA
Nemotron agents read COBOL, record the real COBOL outputs as tests, rewrite each program in
Python, and accept a rewrite only when every output matches exactly. Four people are
extending it in parallel so it can migrate a **multi-file COBOL codebase** (programs share
copybooks and `CALL` each other). You own **one piece: the COBOL runtime**.

## Start

```bash
git fetch origin
git checkout -b codebase/p2-runtime origin/person2/legacy-runtime-harness
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-backend.lock     # needs: brew install gnucobol
python -m pytest -q tests/codebase/test_p2_runtime.py -rs   # 6 tests, all "pending" now
```

Read these first:
- `docs/codebase-support-plan.md`: the whole plan; you are Task 1.
- `contract.py`, section **CODEBASE SUPPORT**: frozen interfaces. Don't change them.
- `legacy/runtime.py`: the existing `compile_cobol`, `_run_process`, `CobolCompileError`, `BIN_DIR`.
- `tests/codebase/test_p2_runtime.py`: your acceptance tests. They define "done".

## Rules

- **Only edit `legacy/runtime.py`.** Every other file belongs to someone else, including the tests,
  fixtures, and `legacy/__init__.py` (which already exports `compile_program`). If you think a test
  is wrong, tell the team. Don't edit it.
- Don't change `compile_cobol`, `run_cobol`, or `record_golden` behavior. The 3 main programs depend on them.
- No network, no new dependencies.

## What to build

Replace the placeholder at the bottom of `legacy/runtime.py`:

```python
def compile_program(cobol_path, link=(), copy_dirs=(), source_format="auto") -> str:
```

- `cobol_path` is the **main** program, the one with the entry point (it ACCEPTs input).
- `link` is a list of `.cbl` subprograms it CALLs, directly or indirectly. They get compiled and
  linked into the **same executable**.
- `copy_dirs` are folders holding copybooks (`COPY INVREC.` → `copybooks/INVREC.cpy`).
- `source_format`: `"free"`, `"fixed"`, or `"auto"`. Auto means try free format first, and if
  that fails, retry fixed, **per file**. A free-format driver must be able to link a fixed-format subprogram.
- Returns the absolute path of the executable.

### Commands proven to work on GnuCOBOL (2026-11-07)

```bash
cobc -c -fixed -I samples/legacy/copybooks -o discount.o samples/legacy/discount.cbl   # each subprogram -> object
cobc -x -free  -o drv tests/fixtures/codebase/drivers/discount_driver.cbl discount.o   # main + objects -> exe
cobc -x -fixed -I samples/legacy/copybooks -o inv samples/legacy/invoice.cbl samples/legacy/discount.cbl
```

You **cannot** pass `-free` and `-fixed` in one cobc command (the flag is global). So compile
each linked file to a `.o` on its own, with its own detected format, then compile the main file
with `-x` plus all the `.o` files.

### Requirements

1. Reuse the safety of `compile_cobol`: `_run_process(command, COMPILE_TIMEOUT_SECONDS)`, catch
   `subprocess.TimeoutExpired`, `OutputLimitExceeded` and `OSError`, and raise `CobolCompileError` with
   the compiler diagnostics (`_diagnostic(...)`). Missing `cobc` → the same clear error message.
2. Validate inputs: every path exists and ends in `.cbl`/`.cob`, and every copy dir is a directory.
   Raise `FileNotFoundError`/`ValueError` like `compile_cobol` does.
3. Build inside a `tempfile.TemporaryDirectory(dir=BIN_DIR)` and `os.replace` the finished binary
   into `BIN_DIR`. A failed build must never replace a previously good binary.
4. **Binary name must depend on everything that changes the result**: the main path, the link
   paths in order, and the copy dirs. Use the sha256 of all of them, like the existing
   `source_id`. Two different link sets must never return the same file.
5. "auto" fallback: if `-free` fails, retry `-fixed`. If both fail, raise `CobolCompileError`
   showing the **fixed** attempt's errors when the file looks fixed-format (column 7 has `*`
   or text starts at column 8), otherwise the free attempt's errors. A missing copybook must
   end in `CobolCompileError`, not a crash.
6. Pass `-I <dir>` for every copy dir to **every** cobc call, both objects and main.
7. Keep it short and readable. About 60 lines is plenty.

### Optional, only if quick

Make `compile_cobol(path)` simply `return compile_program(path, source_format="free")`, so there's
one code path. Only do this if `python -m pytest -q tests/runtime tests/harness` stays green.

## Done when

```bash
CODEBASE_MERGE=1 python -m pytest -q tests/codebase/test_p2_runtime.py   # 6 passed, 0 skipped
python -m pytest -q tests dev/p4                                         # whole suite still green
```

Also check by hand that the sample invoice gives a 12.5% gold discount:

```bash
python -c "import legacy as L; b=L.compile_program('samples/legacy/invoice.cbl', link=['samples/legacy/discount.cbl'], copy_dirs=['samples/legacy/copybooks']); print(L.run_cobol(b,'00020050000G'))"
# SUBTOTAL:    1000.00
# DISCOUNT:   125.00
# NET:          875.00
```

Then commit and push:

```bash
git add legacy/runtime.py
git commit -m "P2: compile_program links CALLed subprograms, copybook dirs, auto format"
git push -u origin codebase/p2-runtime
```

Tell Hemant your branch is ready. If you finish early, help with the demo "bank" codebase
(see the plan) or pair with whoever is still pending.
