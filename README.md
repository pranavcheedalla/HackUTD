# Legacy → Verified

An integrated NVIDIA Nemotron / LangGraph backend that reads COBOL, documents it,
records its real outputs, writes Python, and accepts a rewrite only after exact
string comparisons pass. A local Streamlit dashboard shows progress and evidence.

P1, P2, P3, and P4 are combined on `person2/legacy-runtime-harness` for PR #1.
The shared signatures in `contract.py` are preserved. Hemant owns the merge to main.

## Install on macOS

Python 3.11 and GnuCOBOL are required:

```bash
brew install gnucobol python@3.11
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-backend.lock
python check_setup.py
```

`requirements-backend.lock` pins the full tested backend, NVIDIA client, and dashboard.
`requirements-combined.lock` remains the earlier P1/P2 fixture-demo environment;
use the backend lock for the integrated project and full regression suite.

## Configure NVIDIA

Copy `.env.example` to `.env` and set `NVIDIA_API_KEY` locally. Do not commit it.
Current model slots use `nvidia/nemotron-3.5-lightning-30b-a3b` and
`nvidia/nemotron-3.5-super-vl-120b-a12b`. Both answered live connection checks.
Credentials are machine-local and are not included in handoff archives.

All pipeline calls use `llm.call_llm`. It provides schema-constrained JSON,
validation and repair, bounded request timeouts, retries for transient errors,
atomic response caching, and call metadata without keys or reasoning text.
Permanent authentication/model errors stop immediately. Real P3 failures remain
failures; they do not silently turn into fixture specs or input sets.

Nano drafts each spec; Super reviews it against source and available recorded
examples. Super generates inputs and rewrites; a separate prompt writes unit tests.
Generated prose remains advisory. Actual COBOL recordings decide acceptance.

## Run safely and inspect progress

```bash
python tools/isolated_run.py --mode real
python -m streamlit run ui/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open the printed localhost dashboard URL. Its Start pipeline button launches the
same isolated runner; choose Live NVIDIA models or Offline fixture demo explicitly.
Each session keeps its own `runs/state.json`, specs, goldens, generated Python,
tests, model-call evidence, and log under `runs/sessions/`. The committed 15-case
recordings are preserved. A lock prevents overlapping managed runs.

For one module, add `--only interest`, `--only invoice`, or `--only payroll`.
To bypass response caching for fresh live evidence, set `LLM_CACHE=0`.

The original shared CLI also works: `python run.py legacy/`. It writes directly
into the current checkout and replaces runtime goldens with its generated inputs.
Use the isolated runner for demos and audits.

## Offline fixture demo

```bash
python tools/isolated_run.py --mode fake
```

This executes real COBOL, LangGraph, and pytest with clearly labeled handwritten
agent responses. It makes no model calls. Interest and payroll pass 15 cases;
invoice intentionally rounds on attempt 1, fails two, then repairs on attempt 2.
The state and dashboard label this mode `offline_fixture`.

The direct CLI also supports an intentional failed demo:

```bash
LLM_MODE=fake python run.py --only invoice --demo-scenario exhaust
```

That returns exit code 2 after three attempts, with fixture explanations. It is
not evidence of a live model explanation.

## Verify

```bash
LLM_MODE=fake python -m pytest tests dev/p4 -q
python record_interest.py --check
python record_payroll.py --check
python record_invoice.py --check
python check_integration.py --output runs/person2-smoke.json
python tools/audit_rewrites.py runs/sessions/<session> --output runs/sessions/<session>/extended-audit.json
```

The regression suite covers runtime limits, exact output, false-pass attempts,
branch integration, NVIDIA wrapper behavior with mocked replies, and dashboard
rendering. The held-out audit compares the generated modules with actual COBOL
on additional valid, invalid, whitespace, and mutated inputs; it makes no model calls.

## Programs and acceptance

| Program | Input line | Rules |
| --- | --- | --- |
| interest | principal\|rate_percent\|years | Decimal simple interest; half-up cents |
| payroll | hours\|hourly_rate | Overtime above 40; progressive fictional tax brackets |
| invoice | quantity\|unit_price\|discount_percent | Discount, overflow guard, silent cent truncation |

Each original is under 150 lines, with 15 reviewed handwritten cases and actual
COBOL golden outputs. Live input sets contain 20–30 distinct cases, retaining
reviewed examples and additional audit regressions. P3 distinguishes delimited
text from the 256-character ACCEPT buffer; its static analysis also detects
invoice's truncating MOVE into `PIC 9(5)V99`.

```text
Input:                1|12.35|0.01
Original truncation:  TOTAL=00012.34
Incorrect rounding:   TOTAL=00012.35
```

The graph follows Understand → Spec → Record → Rewrite → Verify → Accept.
Failed comparisons feed exact failures back to the rewrite agent, up to three
attempts; exhaustion produces explanations and a failed module. Generated unit
tests are a supplementary layer and cannot override golden equivalence failures.

Passing proves exact strings for the tested cases, not universal equivalence.
Subprocess limits and isolated run folders are not an OS security sandbox.

See [backend setup and branch audit](docs/backend-setup.md),
[acceptance checklist](docs/ACCEPTANCE_CHECKLIST.md), and
[P2 program details](docs/person2-runtime.md).
