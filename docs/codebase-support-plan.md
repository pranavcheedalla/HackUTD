# Codebase support: 4 parallel tasks

**Goal:** run the pipeline on a real multi-file COBOL codebase, where programs share
copybooks and `CALL` each other. We test it on Abhinav's `samples/legacy`, then on the
demo codebase.

```
samples/legacy/
  discount.cbl        subprogram (no input of its own; called with 3 parameters)
  invoice.cbl         COPY INVREC.  +  CALL 'DISCOUNT'
  interest.cbl        standalone, old fixed-format COBOL
  copybooks/INVREC.cpy
```

**Already proven on GnuCOBOL (2026-11-07):**
- Compiling each file in its own format and then linking them works. INVOICE calls DISCOUNT correctly.
- A generated "driver" program makes a subprogram testable with our one-line input convention.
- The hand-written reference Python matches the real COBOL on all 30 shared test inputs.

## Ready-to-paste prompts (one per person)

Each file is a complete brief for your AI coding assistant: setup, files you own, exact
behavior, known traps, and the commands that prove you're done.

| Person | Prompt |
|---|---|
| Madhav (P2) | [`docs/codebase-prompts/P2-madhav-runtime.md`](codebase-prompts/P2-madhav-runtime.md) |
| Abhinav (P3) | [`docs/codebase-prompts/P3-abhinav-analysis.md`](codebase-prompts/P3-abhinav-analysis.md) |
| Pranav (P4) | [`docs/codebase-prompts/P4-pranav-rewrite.md`](codebase-prompts/P4-pranav-rewrite.md) |
| Hemant (P1) | [`docs/codebase-prompts/P1-hemant-pipeline.md`](codebase-prompts/P1-hemant-pipeline.md) |

## How this stays independent

- The interfaces are frozen in `contract.py`, in the section headed **CODEBASE SUPPORT**. Read it first.
- Each person owns different files. Nobody edits anyone else's files.
- Each person has their own acceptance test file in `tests/codebase/`. Until your piece
  lands, your tests show as *pending* (skipped), never red.
- The reference answers are in `tests/fixtures/codebase/`. They contain Python that matches
  the real COBOL, the shared test inputs, and a hand-written example driver.

## Setup (everyone)

```bash
git fetch origin
git checkout -b codebase/<your-part> origin/person2/legacy-runtime-harness
python -m pip install -r requirements-backend.lock      # Python 3.11 + brew install gnucobol
python -m pytest -q tests/codebase -rs                  # everything "pending" before you start
```

You're done when your own test file passes with **no pending** items, and the full suite is still green:

```bash
CODEBASE_MERGE=1 python -m pytest -q tests/codebase/test_<yours>.py
python -m pytest -q tests dev/p4
```

Then push `codebase/<your-part>` and tell Hemant.

---

## Task 1: Madhav (P2), runtime: compile and link

**Branch:** `codebase/p2-runtime`  **Files:** `legacy/runtime.py` only
**Test:** `tests/codebase/test_p2_runtime.py`

Replace the placeholder `compile_program(cobol_path, link=(), copy_dirs=(), source_format="auto")`:
1. Compile each `link` file to an object file: `cobc -c -o x.o file.cbl`, with every `-I <copy_dir>`.
2. Compile the main file with `cobc -x`, linking those `.o` files, into one executable.
3. `auto` format: try `-free` first, and if that fails, retry `-fixed`. Do this per file, because a free-format driver links to a fixed-format subprogram.
4. The binary cache name must include the link list and copy_dirs, so different links never share a binary.
5. Keep all existing protections: timeouts, output limits, and atomic replace. `compile_cobol()` must keep working unchanged.

The working cobc commands are in the "Already proven" section above.

## Task 2: Abhinav (P3), analysis: dependencies, parameters, driver

**Branch:** `codebase/p3-analysis`
**Files:** `agents/understand.py`, `agents/cobol_static.py`, `agents/driver.py`, `agents/generate_inputs.py`
**Test:** `tests/codebase/test_p3_analysis.py`

1. Each module returned by `understand()` also includes `kind`, `program_id`, `link`
   (absolute callee paths, transitive, callees first), `copy_dirs` (absolute), and `params`.
   Old keys stay unchanged.
2. Parse the LINKAGE SECTION and `PROCEDURE DIVISION USING` into `Param` dicts (see contract).
3. Write `make_driver(src)`. It must behave exactly like `tests/fixtures/codebase/drivers/discount_driver.cbl`:
   UNSTRING on `|`, NUMVAL for numerics, CALL, then one `NAME=value|...` line.
4. `render_summary()` for a subprogram must include the driver input line `LK-TIER|LK-SUBTOTAL|LK-RATE`,
   and `generate_inputs()` must return driver-format lines (20–30).

## Task 3: Pranav (P4), rewrite with dependencies

**Branch:** `codebase/p4-rewrite`  **Files:** `agents/rewrite.py`, `agents/_sandbox.py`, `agents/test_writer.py`
**Test:** `tests/codebase/test_p4_rewrite.py`

1. Add `deps: list[DepInfo] | None = None` to `rewrite()`.
2. Prompt for a caller: include each dependency's accepted Python and its `call()` signature.
   Say: "import <module_id> and use <module_id>.call(...); never re-implement it."
3. Prompt for a subprogram (source has `PROCEDURE DIVISION USING`): require both `call(*params) -> tuple`
   (by-reference: return every param after the call) and `main(line)` in the driver format.
   The literal phrase `NAME=value` must appear in the prompt.
4. Self-check sandbox: write each dependency's Python next to the module being tested,
   so `import discount` works. The first good answer must pass self-check, so only 1 model call is used.
5. The references in `tests/fixtures/codebase/modern/` show the exact conventions.

## Task 4: Hemant (P1), pipeline wiring, run tools, dashboard

**Branch:** `codebase/p1-pipeline`
**Files:** `pipeline/graph.py`, `run.py`, `tools/isolated_run.py`, `ui/*`, `agents/demo.py`, `.gitignore`
**Test:** `tests/codebase/test_p1_pipeline.py`

1. `run.py`: put the new `understand()` keys into each module's start state, plus
   `dep_modules` (module_id, program_id, params, final status of each dependency so far).
2. `graph.record`:
   - For a subprogram: write `agents.make_driver(src)` to `DRIVERS_DIR/<id>_driver.cbl`
     (`DRIVERS_DIR = ROOT/"runs"/"drivers"`), then compile it with
     `link=[cobol_path, *link]`.
   - For a program: `compile_program(cobol_path, link, copy_dirs)`.
3. `graph.rewrite`: build `deps` from `MODERN_DIR/<dep>.py` and pass them as `deps=`.
   If a dependency's status isn't `done`, fail with `blocked: dependency <id> not verified`
   and don't call the model.
4. `tools/isolated_run.py`: add `--legacy-dir`, and let `--only` take any module id.
5. Dashboard: show the migration order as a dependency chain (DISCOUNT → INVOICE),
   with a "subprogram" badge and "blocked" status.

---

## Merge day (one computer, Hemant)

```bash
git checkout person2/legacy-runtime-harness && git pull
git merge origin/codebase/p2-runtime      # runtime first
git merge origin/codebase/p3-analysis
git merge origin/codebase/p4-rewrite
git merge origin/codebase/p1-pipeline     # wiring last
CODEBASE_MERGE=1 python -m pytest -q tests/codebase     # must be 0 failed, 0 skipped
python -m pytest -q tests dev/p4                        # old suite still green
python tools/isolated_run.py --mode real --legacy-dir samples/legacy   # real Nemotron run
python tools/isolated_run.py --mode real                               # 3 main programs still pass
```

The files don't overlap, so merges should be conflict-free. If anything conflicts, it means
someone edited a file they don't own. Keep the owner's version.

**Done** means all of the following:
- 0 pending in merge mode.
- The real sample run migrates DISCOUNT before INVOICE, and all modules are `done`.
- The original 3-program run still passes.
- The dashboard shows the dependency chain.
