# Final real-model evidence (2026-11-07)

Session `20261107-164719-real-92234b`, produced with
`python tools/isolated_run.py --mode real` (NVIDIA Nemotron Nano + Super, live calls).

| Check | Result | File |
| --- | --- | --- |
| Pipeline, all three modules | 3/3 `done`, 90/90 exact matches, 1 attempt each | `state.json`, `pipeline.log` |
| Live model calls | 16 recorded, all `ok`, source `live` | `llm_calls.jsonl` |
| Held-out audit vs actual COBOL | interest 308/308, invoice 312/312, payroll 306/306 | `held_out_audit.json` |
| Invoice divergence path (**controlled mutation**) | see below | `invoice_mutation_*.json` |
| Accepted Python | as generated | `modern/` |

## Controlled mutation (step 6)

The model truncated correctly on its own, so `tools/mutation_check.py` injected a
labeled bug into a *copy* of the accepted session: `pic_store` always rounds half-up.

- Verification caught it: 26/30, including `1|12.35|0.01` expected `TOTAL=00012.34`, got `TOTAL=00012.35`.
- Real explanation agent: `new_code_bug` — "The Python code rounds 12.345 up to 12.35 instead of truncating to 12.34 like COBOL."
- Real rewrite agent repaired it on attempt 1: 30/30, and the repaired module passes the 312-input held-out audit.
- Three-attempt exhaustion with a real explanation was observed earlier in session `20261107-162658-real-f38eab` (payroll, `new_code_bug`: accepted negative input `-1.00`); that defect is fixed in the current prompts.

## Known caveats

- Payroll's supplementary model-written unit tests were rejected (`unit_tests_status: needs_review`):
  Super assumed `999.99|999.99` overflows, but actual COBOL prints `GROSS=1479970.20|…`.
  Golden equivalence is unaffected; the dashboard shows the review flag.
- Verified means exact matches on recorded and audited inputs, not a proof of equivalence for all inputs.
- The generated `invoice.py` references `ROUND_HALF_UP` without importing it in a branch no COBOL
  statement reaches (`ROUNDED` is never used by invoice); harmless today, worth noting for reviewers.
