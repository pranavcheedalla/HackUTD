# Prompt for Abhinav (P3): codebase analysis, dependencies, parameters, test driver

> Paste everything below this line into your AI coding assistant (Claude Code / Codex),
> opened in your HackUTD checkout.

---

You are working on **HackUTD "Legacy → Verified"**. It's a hackathon project: NVIDIA
Nemotron agents read COBOL, record the real COBOL outputs as tests, rewrite each program in
Python, and accept a rewrite only when every output matches exactly. Four people are
extending it in parallel so it can migrate a **multi-file COBOL codebase** (programs share
copybooks and `CALL` each other). You own **the analysis piece**: what calls what, what
parameters a subprogram takes, and a generated COBOL "test driver" so a subprogram (which has
no input of its own) can be tested with our one-line-in / one-line-out convention.

## Start

```bash
git fetch origin
git checkout -b codebase/p3-analysis origin/person2/legacy-runtime-harness
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-backend.lock     # needs: brew install gnucobol
python -m pytest -q tests/codebase/test_p3_analysis.py -rs   # 1 passes, 6 "pending" now
```

Read these first:
- `docs/codebase-support-plan.md`: the whole plan; you are Task 2.
- `contract.py`, section **CODEBASE SUPPORT**: `Param`, `CodebaseModule`, the `make_driver` contract. Frozen.
- `samples/legacy/`: `discount.cbl` (subprogram), `invoice.cbl` (`COPY INVREC.` + `CALL 'DISCOUNT'`),
  `interest.cbl` (standalone), `copybooks/INVREC.cpy`.
- `tests/fixtures/codebase/drivers/discount_driver.cbl`: **the hand-written driver your generator must reproduce**.
- `tests/fixtures/codebase/modern/discount.py` + `inputs.json`: expected behavior, verified against real COBOL.
- `tests/codebase/test_p3_analysis.py`: your acceptance tests. They define "done".

## Rules

- **Only edit:** `agents/understand.py`, `agents/cobol_static.py`, `agents/driver.py`, `agents/generate_inputs.py`
  (and `agents/extract_spec.py` only if step 5 needs it).
  Don't edit tests, fixtures, `contract.py`, `agents/__init__.py` (it already exports `make_driver`), or other people's files.
- The 3 main programs in `legacy/` must keep working exactly as today. Their input-format handling
  and the 15 reviewed cases are tested in `tests/p3` and `tests/pipeline`.

## What to build

### 1. `understand()` returns the codebase keys (`agents/understand.py`)

Keep every existing key (`module_id`, `cobol_path`, `depends_on`, `program_id`, `copybooks`,
`unresolved_calls`) and the callees-first order. **Add** to every module:

| key | value for the samples |
|---|---|
| `kind` | `"subprogram"` if `PROCEDURE DIVISION USING ...`, else `"program"` |
| `link` | absolute `.cbl` paths of **all** callees, transitively, callees first, no self. invoice → `[<abs>/samples/legacy/discount.cbl]` |
| `copy_dirs` | absolute, de-duplicated parent folders of the module's copybooks. invoice → `[<abs>/samples/legacy/copybooks]` |
| `params` | subprograms: list of `Param` in USING order; programs: `[]` |

Use `str(Path(...).resolve())` for absolute paths. Build `link` with a depth-first walk over
`depends_on`, emitting callees before callers and skipping duplicates (A→B→C gives `[C, B]` for A).

### 2. `Param` parsing (`agents/cobol_static.py`)

The data-division parser already reads LINKAGE fields correctly. `analyze(discount_src).fields`
gives `Field(section, name, pic, kind, int_digits, decimals, length, signed)`:

```
LINKAGE  LK-TIER      'X'        alphanumeric  0 0 1 False
LINKAGE  LK-SUBTOTAL  '9(7)V99'  numeric       7 2 9 False
LINKAGE  LK-RATE      '9(2)V99'  numeric       2 2 4 False
```

Add `linkage_params(src) -> list[dict]`. It reads the names after `PROCEDURE DIVISION USING`
(stop at the period; ignore `BY REFERENCE`/`BY VALUE` words), looks each up in the index, and returns:
`{"name", "pic" (as written), "kind": "numeric"|"text", "int_digits", "dec_digits", "length", "signed"}`.
- Group items (01 with children) count as `"text"` of their total length.
- Also add `kind` and `params` to the `Analysis` dataclass, filled in `analyze()`.
- The test expects exactly the `DISCOUNT_PARAMS` list in `tests/codebase/test_p3_analysis.py`.

### 3. `make_driver(subprogram_src) -> str` (`agents/driver.py`)

Generate **free-format** COBOL that behaves exactly like `discount_driver.cbl`:

```
PROGRAM-ID. DRV-<PROGRAM-ID>.
WORKING-STORAGE: IN-LINE PIC X(256); for each param i:
   Ti PIC X(64)          token
   Pi PIC <same pic>     the actual argument (keep S if signed)
   Ei edited copy        numeric only: PIC 9(int).9(dec); "9(int)" if dec = 0; "-9(int).9(dec)" if signed
PROCEDURE: ACCEPT IN-LINE
           UNSTRING IN-LINE DELIMITED BY "|" INTO T1 T2 ... Tn
           numeric: COMPUTE Pi = FUNCTION NUMVAL(Ti)      text: MOVE Ti TO Pi
           CALL '<PROGRAM-ID>' USING P1 ... Pn
           numeric: MOVE Pi TO Ei
           DISPLAY "<NAME1>=" <P1 or E1> "|<NAME2>=" ... (ONE line)
           STOP RUN.
```

- Use short generated names (`T1`, `P1`, `E1`). COBOL names max out at 30 characters.
- If a numeric param has 0 integer digits (`PIC V99`), use edited `PIC .9(d)`.
- Raise `ValueError` with a clear message if the source has no `PROCEDURE DIVISION USING`.
- The test compiles your driver with plain `cobc` against the real `discount.cbl` and compares
  all 10 inputs in `inputs.json` with the reference. Empty fields must behave like the reference
  (`NUMVAL("")` = 0, empty text = space).

### 4. Driver-format inputs (`agents/cobol_static.py` + `agents/generate_inputs.py`)

- `render_summary()` for a subprogram must say:
  `INPUT LINE (test driver): LK-TIER|LK-SUBTOTAL|LK-RATE`, then one line per param with its PIC
  meaning. Then `OUTPUT LINE (test driver): LK-TIER=...|LK-SUBTOTAL=9(7).99|LK-RATE=9(2).99`.
- Simplest way to reuse the existing pipe-delimited flow: for a subprogram, set
  `analysis.delimiter = "|"` and fill `delimited_fields` from the params (same keys as today:
  name, raw, pic, type, meaning). `extract_spec` then describes the spec's inputs as tokens too.
- `generate_inputs()` must return 20–30 driver-format lines (exactly n-1 `|` for n params).
  Cover each EVALUATE/IF branch: each tier code, a lowercase/invalid code, thresholds just
  below/at/above (999.99 / 1000.00 / 1000.01), zero, max values, and empty tokens.
  The 15 reviewed cases only apply to the 3 `legacy/` programs. Check that `_anchors()` still returns `[]` here.

### 5. Sanity check with a real model (optional, uses your NVIDIA key in `.env`)

```bash
python -c "
from agents import extract_spec, generate_inputs
src=open('samples/legacy/discount.cbl').read(); s=extract_spec(src); print(s['summary']); print(generate_inputs(s, src)[:5])"
```

The spec should describe the parameters, not an input line it doesn't have.

## Done when

```bash
CODEBASE_MERGE=1 python -m pytest -q tests/codebase/test_p3_analysis.py   # 7 passed, 0 skipped
python -m pytest -q tests dev/p4                                           # whole suite still green
python -c "import agents,json;print(json.dumps(agents.understand('samples/legacy'),indent=1))"   # eyeball it
```

Then commit and push:

```bash
git add agents/understand.py agents/cobol_static.py agents/driver.py agents/generate_inputs.py
git commit -m "P3: codebase analysis - link/copy_dirs/kind/params, subprogram test driver"
git push -u origin codebase/p3-analysis
```

Tell Hemant your branch is ready. If you finish early, you're the best person to write the
demo "bank" codebase (5–6 programs, 2 copybooks, a CALL chain).
