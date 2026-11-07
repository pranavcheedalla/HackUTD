# Prompt for Hemant (P1): pipeline wiring, run tools, dashboard, merge

> Paste everything below this line into your AI coding assistant (Claude Code / Codex),
> opened in your HackUTD checkout.

---

You are working on **HackUTD "Legacy → Verified"**. It's a hackathon project: NVIDIA
Nemotron agents read COBOL, record the real COBOL outputs as tests, rewrite each program in
Python, and accept a rewrite only when every output matches exactly. Four people are
extending it in parallel so it can migrate a **multi-file COBOL codebase** (programs share
copybooks and `CALL` each other; e.g. `INVOICE` calls the subprogram `DISCOUNT`). You own
**the pipeline wiring**: LangGraph nodes, `run.py`, the isolated runner, and the dashboard.
You are also the **merger**.

## Start

```bash
git fetch origin
git checkout -b codebase/p1-pipeline origin/person2/legacy-runtime-harness
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-backend.lock     # needs: brew install gnucobol
python -m pytest -q tests/codebase/test_p1_pipeline.py -rs   # 5 tests, all "pending" now
```

Read these first:
- `docs/codebase-support-plan.md`: the whole plan; you are Task 4, plus the merge.
- `contract.py`, section **CODEBASE SUPPORT**: the keys `understand()` will return, `DepInfo`, and the P1 rules. Frozen.
- `pipeline/graph.py`, `run.py`, `tools/isolated_run.py`, `ui/app.py`, `ui/dashboard_data.py`, `agents/demo.py`.
- `tests/codebase/test_p1_pipeline.py`: your acceptance tests. They define "done". The module docstring lists the state keys.

## Rules

- **Only edit:** `pipeline/graph.py`, `run.py`, `tools/isolated_run.py`, `ui/*`, `agents/demo.py`, `.gitignore`.
  Don't edit tests, fixtures, `contract.py`, or teammates' files.
- Until the others merge, `legacy.compile_program` and `agents.make_driver` are placeholders that
  raise `NotImplementedError`, and `understand()` doesn't return the new keys yet. Your tests stub them,
  so you can finish without waiting. Write code that reads the new keys with safe defaults
  (`m.get("kind", "program")`, `m.get("link", [])`, ...).
- `LLM_MODE=fake python run.py legacy/` (the offline demo) and the real 3-program run must keep working.

## What to build

### 1. `GraphState` must declare the new keys. This is a trap.

LangGraph **silently drops state keys that aren't declared** in the `GraphState` TypedDict (verified:
an undeclared key vanishes after one node). Add `kind`, `program_id`, `link`, `copy_dirs`, `params`,
`depends_on`, `dep_modules` to `GraphState`, or every node will see them missing.

### 2. `run.py`: pass codebase info into each module's start state

For each module from `agents.understand(dir)`, add to `init`:

```python
"kind": m.get("kind", "program"), "program_id": m.get("program_id", ""), "link": m.get("link", []),
"copy_dirs": m.get("copy_dirs", []), "params": m.get("params", []), "depends_on": m.get("depends_on", []),
"dep_modules": [{"module_id": d, "program_id": by_id[d].get("program_id", ""),
                 "params": by_id[d].get("params", []),
                 "status": results.get(d, {}).get("status", "not run")} for d in m.get("depends_on", [])],
```

- If any dependency isn't `done`, don't invoke the graph at all (saves model calls). Mark the module
  failed with `error = "blocked: dependency <id> not verified"` through `status.update(...)`, add
  it to `results`, print it, and continue.
- `--only X`: also run X's dependencies first (transitively, in understand order). Otherwise X is
  always blocked. Print `Migration order:` with the actual list.

### 3. `pipeline/graph.py`: nodes

- Add `DRIVERS_DIR = ROOT / "runs" / "drivers"` (tests patch it).
- **`record`**:
  - subprogram (`state["kind"] == "subprogram"`):
    `driver = DRIVERS_DIR / f"{id}_driver.cbl"`, write `agents.make_driver(state["cobol_src"])` to it, then
    `legacy.compile_program(str(driver), link=[state["cobol_path"], *state["link"]], copy_dirs=state["copy_dirs"])`.
    The inputs from `agents.generate_inputs` are already in driver format.
  - program: `legacy.compile_program(state["cobol_path"], link=state["link"], copy_dirs=state["copy_dirs"])`.
  - Then `legacy.record_golden(...)` exactly as today.
- **`rewrite`**:
  - First, if any `dep_modules` entry has `status != "done"`, **return** (don't raise) `{**state, "status": "failed",
    "error": f"blocked: dependency {id} not verified"}` and call `status.update`. Raising inside
    a node gets wrapped by `_safe` as `"rewrite: ValueError: ..."`, and the test checks that the error
    *starts with* `blocked:`. Don't call the model.
  - Build `deps = [{"module_id", "program_id", "params", "python_src": (MODERN_DIR / f"{id}.py").read_text()}]`.
  - Call `agents.rewrite(spec, src, failures, deps=deps)` **only when `deps` is non-empty**. Otherwise use the
    old 3-argument call. The offline demo's fake `rewrite(spec, source, failures)` in
    `agents/demo.py` doesn't accept `deps`. Also give it `**kwargs` there.
- Equivalence tests already put `modern/` on `sys.path`, so `import discount` works there. No change needed.

### 4. `tools/isolated_run.py`

- Add `--legacy-dir` (default `legacy`). It is relative to the session copy, so pass
  `str(session / args.legacy_dir)` as run.py's positional `legacy_dir`. Store it in `session.json`.
- `--only` takes any module id (remove the fixed `choices`).
- Note: `copytree` ignores every folder named `modern`, `bin`, `specs`, ... at any depth. That's fine
  (fixtures aren't needed in a session), but don't add a codebase folder with one of those names.
- Add `runs/drivers/` to `.gitignore`.

### 5. Dashboard (`ui/app.py`, `ui/dashboard_data.py`)

`status.update` already persists every state key except source text, so `kind`, `depends_on`, `link`
and `error` appear in `runs/state.json` for free.
- Show the migration order as a chain, using `depends_on`, e.g. `DISCOUNT  →  INVOICE`, with standalone modules listed beside it.
- Add a **subprogram** badge, and a clear **BLOCKED** status (gray, with "waiting on discount"), distinct from failed.
- In each module's panel, show what it links/calls and which copybooks it uses.
- Keep "real model vs offline fixture" labeling exactly as is.

## Done when

```bash
CODEBASE_MERGE=1 python -m pytest -q tests/codebase/test_p1_pipeline.py   # 5 passed, 0 skipped
python -m pytest -q tests dev/p4                                          # whole suite still green
LLM_MODE=fake python run.py legacy/                                       # offline demo still 3/3
```

Commit and push `codebase/p1-pipeline`.

---

## Merge (you, on one computer, after all four branches are pushed)

```bash
git checkout person2/legacy-runtime-harness && git pull
git merge --no-ff origin/codebase/p2-runtime    # Madhav: runtime first
git merge --no-ff origin/codebase/p3-analysis   # Abhinav
git merge --no-ff origin/codebase/p4-rewrite    # Pranav
git merge --no-ff origin/codebase/p1-pipeline   # you: wiring last

CODEBASE_MERGE=1 python -m pytest -q tests/codebase    # must be: 0 failed, 0 skipped
python -m pytest -q tests dev/p4                       # old suite green
LLM_MODE=fake python run.py legacy/                    # offline demo 3/3
python tools/isolated_run.py --mode real --legacy-dir samples/legacy
python tools/isolated_run.py --mode real               # original 3 programs still pass
python -m streamlit run ui/app.py --server.address 127.0.0.1
```

The files don't overlap, so there should be no conflicts. If one appears, someone edited a file they
don't own. Keep the owner's version and tell them.

**Done** means all of the following:
- 0 pending in merge mode.
- The real sample run prints `Migration order:` with `discount` before `invoice`, and all modules are `done`.
- The 3-program run still passes.
- The dashboard shows the DISCOUNT → INVOICE chain.

Save the session folder as evidence under `docs/evidence/`, the way the 2026-11-07 run was saved.
Push the branch, which updates PR #1, then merge PR #1 into `main`.
