# Multi-file codebase: final real-model evidence (2026-11-07)

`python tools/isolated_run.py --mode real --legacy-dir samples/legacy`, session
`20261107-180027-real-27d0f7`, after merging the four `codebase/*` branches.

| Check | Result |
| --- | --- |
| Migration order from CALL analysis | `discount -> interest -> invoice` (callee before caller) |
| Pipeline | 3/3 `done`, 72/72 exact matches, 1 attempt each, 19 live Nemotron calls |
| Subprogram testing | DISCOUNT recorded through the generated driver (`NAME=value` lines) |
| Caller uses verified callee | `modern/invoice.py` does `import discount` / `discount.call(...)`; no discount rules copied |
| Held-out audit vs actual COBOL | 480/480 (discount 160, interest 158, invoice 162) |
| Regression: original 3 programs, real run | 3/3, 90/90; held-out audit 926/926 |
| Tests | 316 passed; `CODEBASE_MERGE=1 pytest tests/codebase` 23/23, 0 pending |

## Bug found only by the live run, fixed at merge

Super was asked to type fixed-width records itself and miscounted columns (26 of 27 invoice
inputs had the wrong width, so the COBOL read the tier letter as a price digit). Fixed-width
programs now use **record mode**: the model returns one value per field and code encodes the exact
columns, dropping values that can't fit. If the model returns too few, deterministic
boundary records top it up. Regression tests are in `tests/p3/test_understanding_agents.py`.
