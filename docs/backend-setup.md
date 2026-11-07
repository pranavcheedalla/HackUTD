# Integrated backend setup and branch audit

## 1. Combine the actual branches

Fetched all remote branches and checked the code, rather than relying on branch names.

| Branch | Inspected commit | Role |
| --- | --- | --- |
| main | 78ce59a | Initial README; final merge stays with Hemant |
| hemant/pipeline-skeleton | ee58f2f | P1 contract, shared client, graph, CLI, status |
| abhinav/understand_agents | 853577c | P3 source/dependency analysis, spec and inputs |
| Pranav | fcde03b | P4 rewrite, unit tests, divergence explanation; includes P1 |
| person2/legacy-runtime-harness | e0fe750 before these merges | P1/P2 integration and hardened runtime |

P3 and P4 were merged into the integration branch with their histories retained.
Their contracts remain compatible; no production agent stub is used in real mode.
The obsolete legacy.py is absent and HELLO stays outside module discovery.

## 2. Correct the P3/P2 I/O mismatch

The original parser mistook `ACCEPT input-line PIC X(256)` for an external fixed-width
record. All three P2 programs actually UNSTRING a pipe-delimited text line. Static
analysis now follows that delimiter and NUMVAL field mapping. P3's independent
fixed-width sample programs keep their original layouts.

The input agent retains all 15 reviewed examples, then audit regressions and model
proposals, deduplicated and capped at 30. It rejects empty model proposals in real
mode. A byte buffer capacity is never used as input padding for these programs.
Static analysis also detects the invoice's numeric MOVE from six fractional digits
into the two-decimal receiving field.

## 3. Configure NVIDIA locally

Create or retrieve a key through the NVIDIA account and put it in ignored `.env`.
Use owner-only file permissions. The local integration machine is configured;
other teammates must configure their own local credentials.

The current Nano and Super model IDs are in `.env.example`. Both passed live
connection checks. The pipeline rejects missing credentials or SDK dependencies
before state mutation, and rejects the P4 local-client bypass.

## 4. Make model outputs usable and inspectable

Every production agent uses the shared wrapper. JSON schemas are sent as NVIDIA
response-format constraints, then checked locally; invalid JSON gets one repair.
Responses are never accepted merely because they contain some JSON text.

Requests have a timeout, bounded retries, immediate failure for permanent 4xx
errors, and no empty-answer caching. Cache writes are atomic. Per-call evidence
records model ID, live/cache source, duration, and success; it contains no API key,
prompt text, or private reasoning. P3 API errors remain visible failures in real mode.

Nano's first drafts contained incorrect arithmetic, padding, and validation prose.
The spec prompt now includes available exact-source COBOL observations, and a
separate Super review checks the draft. Source and golden outputs always take
precedence over prose in a rewrite. This is an improvement, not a proof that all
model-written spec statements are correct.

## 5. Verify the real rewrite loop

Run `python tools/isolated_run.py --mode real`. It runs the public graph in a fresh
session copy, keeps credentials in the parent environment, and preserves the
committed references. Each session contains its full state, source, goldens,
equivalence tests, logs, and real/cache call evidence.

Live testing exposed a rewrite that reset a shared validity flag for every field.
The rewrite prompt now explicitly preserves COBOL working-storage state across
PERFORM calls. It also preserves ASCII-space-only TRIM rather than Python's broader
bare strip(), and distinguishes zero-preserving 9 pictures from suppressing Z.

## 6. Challenge the accepted modules

Run `tools/audit_rewrites.py` against a session. Its fresh data includes 128 seeded
numeric combinations per module, 200 mutation attempts, reviewed cases, and
whitespace/leading-zero/cent-boundary examples. Every expected result comes from
the actual COBOL executable. This audit is separate from the model-selected golden
set so weak generated coverage cannot hide a mismatch.

P4's preliminary execution checks also use bounded output and process-group cleanup,
and register imported modules so generated dataclasses work. Child environments
omit common credential variables. These subprocess controls do not provide an OS
sandbox or make arbitrary generated code safe to run against sensitive files.

## 7. Inspect the Streamlit dashboard

Run `python -m streamlit run ui/app.py --server.address 127.0.0.1`.
The dashboard reads session state every two seconds and distinguishes real-model
execution from offline fixtures. It shows exact matches, attempts, specs, COBOL and
Python, mismatches, explanations, phase events, and model-call evidence.

Start pipeline launches a managed isolated run; a lock prevents overlapping managed
runs. Artifact reads are restricted to allowlisted source/spec paths and session
directories. The API key is never rendered. Keep this demo dashboard on localhost.

## 8. Validate and hand off

Install `requirements-backend.lock` with Python 3.11 and GnuCOBOL, then run the full
regression suite and all three recording checks as shown in README. Review the
real session state and held-out audit separately from offline fixture evidence.

Publish the integration branch to PR #1 with validation evidence. Hemant reviews
and performs the final merge into main. A successful fixture run, a successful
connection check, and a fully verified real migration are different milestones;
the release evidence must state which was actually achieved.

## 9. Achieved milestone (2026-11-07)

A fully verified real migration was achieved, not just a fixture run or connection
check. Evidence is in `docs/evidence/2026-11-07-final-real-run/`:

- Real run: 3/3 modules `done`, 90/90 exact matches, 16 live Nemotron calls.
- Held-out audit against actual COBOL: 926/926 (interest 308, invoice 312, payroll 306).
- Invoice divergence path: `python tools/mutation_check.py <session>` injects a labeled
  rounding bug into a session copy. Verification caught `00012.34` vs `00012.35`, the real
  explainer attributed it to rounding instead of COBOL truncation, and the real rewrite
  repaired it (30/30, 312/312 held-out).
- Regression suite: 291 passed.
- Open item: payroll's supplementary model-written unit tests are flagged `needs_review`
  because they asserted a wrong overflow expectation; golden equivalence is unaffected.

Generated input replies are now size-bounded (`maxItems`, string `maxLength`, and only the
remainder after the 15 reviewed cases is requested). An unbounded Super reply previously
grew past 32K characters and failed JSON parsing for interest.
