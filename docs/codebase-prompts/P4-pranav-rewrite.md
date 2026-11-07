# Prompt for Pranav (P4): rewrite with dependencies

> Paste everything below this line into your AI coding assistant (Claude Code / Codex),
> opened in your HackUTD checkout.

---

You are working on **HackUTD "Legacy → Verified"**. It's a hackathon project: NVIDIA
Nemotron agents read COBOL, record the real COBOL outputs as tests, rewrite each program in
Python, and accept a rewrite only when every output matches exactly. Four people are
extending it in parallel so it can migrate a **multi-file COBOL codebase**. There, programs
`CALL` each other: `INVOICE` calls the subprogram `DISCOUNT`. The pipeline migrates callees
first. You own **the rewrite agent**. When it rewrites a caller, it must receive the
already-verified Python of each callee and **import it** instead of re-implementing it. When it
rewrites a subprogram, it must produce the subprogram calling convention.

## Start

```bash
git fetch origin
git checkout -b codebase/p4-rewrite origin/person2/legacy-runtime-harness
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-backend.lock     # needs: brew install gnucobol
python -m pytest -q tests/codebase/test_p4_rewrite.py -rs   # 4 tests, all "pending" now
```

Read these first:
- `docs/codebase-support-plan.md`: the whole plan; you are Task 3.
- `contract.py`, section **CODEBASE SUPPORT**: `DepInfo`, `Param`, the rewrite contract. Frozen.
- `tests/fixtures/codebase/modern/discount.py` and `invoice.py`: **the exact conventions** your
  prompt must make the model produce. They're verified against real COBOL.
- `samples/legacy/discount.cbl` and `invoice.cbl`: the COBOL they came from.
- `agents/rewrite.py` (`REWRITE_SYSTEM`, `REWRITE_USER`, `FIX_SECTION`, `rewrite`, `self_check`, `validate`)
  and `agents/_sandbox.py` (`run_main`, `run_pytest`).
- `tests/codebase/test_p4_rewrite.py`: your acceptance tests. They define "done".

## Rules

- **Only edit `agents/rewrite.py` and `agents/_sandbox.py`** (and `agents/test_writer.py` if step 5 needs it).
  Don't edit tests, fixtures, `contract.py`, or other people's files.
- All model calls keep going through `_llm.call_llm` (the shared NVIDIA wrapper).
- Rewrites of the 3 existing programs (no deps) must behave exactly as today. Run `dev/p4` and `tests` often.

## The conventions (from `contract.py`)

- **Every module:** `def main(input_line: str) -> str`.
- **Subprogram** (COBOL has `PROCEDURE DIVISION USING ...`):
  - `def call(*params) -> tuple`: params in USING order (Decimal for numeric, str for text).
    Returns **every** param after the call, because COBOL passes BY REFERENCE and the callee can change any of them.
  - `main(input_line)` uses the **test-driver format**. The input is the params joined by `|`
    (numbers as decimal text). The output is one line `NAME=value|NAME=value|...` with each numeric value
    zero-padded as `9(int).9(dec)` and text as stored. Example:
    `main("G|100.00|0") == "LK-TIER=G|LK-SUBTOTAL=0000100.00|LK-RATE=12.50"`.
- **Caller:** `import discount` (the callee's module_id), then
  `tier, subtotal, rate = discount.call(tier, subtotal, rate)`. Never re-implement the callee.
  `modern/` is on `sys.path` when equivalence tests run.

## What to build

### 1. `rewrite(spec, cobol_src, failures=None, previous_src=None, deps=None) -> str`

`deps` is `list[DepInfo]`: `{"module_id", "program_id", "params", "python_src"}` for each callee,
already verified. Keep `deps=None` meaning exactly today's behavior.

### 2. Prompt sections (`agents/rewrite.py`)

Add a `DEPS_SECTION`, included whenever `deps` is non-empty, **including on retries** (alongside `FIX_SECTION`).
For each dependency include:
- `CALL '<program_id>'` maps to `import <module_id>` and `<module_id>.call(...)`, written out with the
  real module id. For example, the text must contain `discount.call`.
- Its parameter table (name, PIC, numeric/text, digits).
- Its full verified Python source in a ```python block.
- Rules: don't copy or re-implement it, pass arguments in USING order, and use the returned tuple
  (by-reference results). Keep the caller's own field truncation when it MOVEs results.

Add a `SUBPROGRAM_SECTION`, included when `re.search(r"PROCEDURE\s+DIVISION\s+USING", cobol_src, re.I)`.
It explains both functions above. It must contain the literal text `def call(` and `NAME=value`,
plus the example line. Also tell the model that a subprogram never ACCEPTs or DISPLAYs.
Its outputs are the params after the call.

### 3. `validate()`

For a subprogram, also require a top-level `def call(`. Return a clear error otherwise, so
self-check asks the model to fix it.

### 4. Sandbox must see the dependencies (`agents/_sandbox.py`). This is the key trap.

`run_main` currently writes only `candidate.py` into a temp dir and runs Python with **`-I`**
(isolated mode). That does **not** put the script's own folder on `sys.path`, so
`import discount` fails even if `discount.py` sits next to it. Fix both parts:
- `run_main(code, inputs, timeout=20, modules: dict[str, str] | None = None)`: write each
  `{module_id}.py` into the temp dir.
- In `_DRIVER`, add the candidate's folder to the path before loading:
  `sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[1])))` (and `import os`).
- `self_check(code, failures, deps=None)` passes `{d["module_id"]: d["python_src"] for d in deps}`.

The test checks that the first correct answer passes self-check, so **exactly 1 model call** is made.
If the dependency isn't importable, self-check fails and the agent wastes retries.

### 5. Unit-test writer sandbox (`run_pytest`)

When a caller's generated unit tests run, `modern/invoice.py` does `import discount`. In
`run_pytest`, also copy every accepted module from the project's `modern/*.py` (except the target)
into `<tmp>/modern/`, and add `<tmp>/modern` to `PYTHONPATH` (`d + os.pathsep + d/modern`).
Callees are always accepted before callers, so they exist by then.

### 6. Don't break

- `explain_divergence` and `write_unit_tests` signatures stay the same.
- Hemant's pipeline will call `agents.rewrite(spec, src, failures, deps=[...])` only for modules with
  dependencies. Your function must also accept being called positionally as before.

## Done when

```bash
CODEBASE_MERGE=1 python -m pytest -q tests/codebase/test_p4_rewrite.py   # 4 passed, 0 skipped
python -m pytest -q tests dev/p4                                         # whole suite still green
```

Optional live check (your NVIDIA key in `.env`). Rewrite DISCOUNT, then INVOICE with DISCOUNT as a dep,
and compare both with the references on `tests/fixtures/codebase/inputs.json`:

```bash
python - <<'EOF'
import json, sys, importlib.util, tempfile, pathlib
from agents import rewrite
src = lambda n: open(f'samples/legacy/{n}.cbl').read()
d = pathlib.Path(tempfile.mkdtemp()); sys.path.insert(0, str(d))
disc = rewrite({"module_id": "discount"}, src("discount")); (d/"discount.py").write_text(disc)
dep = {"module_id": "discount", "program_id": "DISCOUNT", "params": [], "python_src": disc}
(d/"invoice.py").write_text(rewrite({"module_id": "invoice"}, src("invoice"), deps=[dep]))
sys.path.insert(0, "tests/fixtures/codebase/modern")
inputs = json.load(open("tests/fixtures/codebase/inputs.json"))
for name in ("discount", "invoice"):
    gen = importlib.util.spec_from_file_location("g_"+name, d/f"{name}.py"); g = importlib.util.module_from_spec(gen); gen.loader.exec_module(g)
    ref = __import__(name)
    bad = [i for i in inputs[name] if g.main(i) != ref.main(i)]
    print(name, "mismatches:", bad)
EOF
```

(The real pipeline also gives the model a spec and recorded failures, so a mismatch here is a hint, not a blocker.)

Then commit and push:

```bash
git add agents/rewrite.py agents/_sandbox.py agents/test_writer.py
git commit -m "P4: rewrite with verified dependencies; subprogram call() convention; sandbox imports deps"
git push -u origin codebase/p4-rewrite
```

Tell Hemant your branch is ready.
