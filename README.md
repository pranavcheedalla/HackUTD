# Legacy Modernization Agents — combined P1 + P2

The system records what original COBOL actually does, rewrites it in Python,
and accepts a rewrite only when its outputs match the recorded cases exactly.

Hemant's contract, LLM wrapper, LangGraph graph, CLI, and atomic state writer are
combined with Person 2's real GnuCOBOL runtime, hardened pytest harness, and all
three demo originals. The shared contract and five public P2 signatures are unchanged.

## Run the combined offline demo

Python 3.11 and GnuCOBOL are required. From the repository root:

```bash
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install gnucobol python@3.11
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-combined.lock
python check_setup.py
LLM_MODE=fake python run.py
```

This runs the **actual COBOL and LangGraph**, using explicitly labeled handwritten
agent fixtures. It calls no model. Interest and payroll pass their 15 cases on
attempt 1. Invoice initially rounds instead of truncating, fails 2 cases, receives
the failure list, and passes all 15 after repair on attempt 2.

Expected final result: `3/3 modules verified`. `runs/state.json` records every
phase and has `mode: "offline_fixture"`, so the dashboard can distinguish this
from a real-model run. Golden records stay identical to the committed 15-case
references. Generated source, tests, specs, caches, and live state are gitignored.

To demonstrate the terminal failure and explanation route:

```bash
LLM_MODE=fake python run.py --only invoice --demo-scenario exhaust
```

That intentionally exits 2 after three attempts: invoice stays 13/15, and the
fixture explainer labels the two differences `legacy_quirk`. Its explanation is
marked as an offline fixture. It is not a Nemotron explanation.

The genuine legacy quirk is easy to inspect:

```text
Input:                1|12.35|0.01
Original truncation:  TOTAL=00012.34
Incorrect rounding:   TOTAL=00012.35
```

## Tests and component checks

```bash
python -m pytest -q
python record_interest.py --check
python record_payroll.py --check
python record_invoice.py --check
python check_integration.py --output runs/person2-smoke.json
```

Run the regression suite in a clean checkout. A demo creates extra generated
equivalence tests against its generated modules; those are ordinary pytest files
and will also be discovered until removed. Live model runs should use a separate
checkout/worktree because their generated input sets replace runtime recordings.

The component smoke uses temporary data and preserves saved references. The
adversarial suite covers false-pass paths, resource limits, cache drift, and
malformed data. See the [acceptance checklist](docs/ACCEPTANCE_CHECKLIST.md) and
[audit report](docs/ADVERSARIAL_REVIEW.md). These checks are not an OS sandbox.

## Real-model mode and next integration steps

P3 and P4 are **still stubs in this combined branch**. `python run.py` defaults to
real mode and stops before execution while those stubs remain. It cannot report
an offline fixture run as real model success.

1. Integrate and review the real understanding agents. The fetched branch
   `abhinav/understand_agents` contains that work; it is not silently merged here.
2. Integrate the real building/rewrite/test-writer/divergence agents. The fetched
   `Pranav` branch currently contains only the initial README.
3. Install `requirements.txt`, copy `.env.example` to `.env`, fill the NVIDIA key,
   and verify the exact Nano/Super model IDs. Never commit `.env`.
4. Use `python llm.py` for Hemant's connection smoke, then `python run.py legacy/`.
5. Verify real model specs/inputs, retry behavior, explanations, and final dashboard.

Every real LLM call must go through `llm.call_llm`. No key is needed for the offline
combined demo. `requirements-combined.lock` pins its tested dependencies;
`requirements.txt` is Hemant's full real-mode dependency list.

## Pipeline and ownership

```text
understand (CLI)
  -> extract_spec -> record -> rewrite -> verify -> accept
                                ^          |
                                +--retry---+
                                           +-> explain -> failed (after 3 attempts)
```

The graph records real outputs and generates pytest tests against `main(input_line)
from each rewritten module. Passing means exact strings for the selected cases,
not mathematical proof for every possible input. Money in Python uses Decimal.

| Piece | Owner | Combined status |
| --- | --- | --- |
| contract.py, llm.py, pipeline/, run.py | Hemant | Integrated; offline graph and state flow verified |
| legacy/ package, testing.py, testing_reporter.py, originals/goldens | P2 | Real implementations integrated |
| agents/understanding.py | P3 | Stub pending real branch integration |
| agents/building.py | P4 | Stub pending real implementation |
| agents/demo.py | Integration fixture | Used only with LLM_MODE=fake |

Hemant retains the final merge into main. This branch combines both histories
for a single reviewable handoff; it does not replace the remaining agent work.

## Program details

| Original | Lines | Handwritten golden cases | Rules |
| --- | --- | --- | --- |
| interest | 99 | 15 | [Runtime and interest guide](docs/person2-runtime.md) |
| payroll | 104 | 15 | [Payroll rules and cases](docs/payroll.md) |
| invoice | 101 | 15 | [Invoice truncation and cases](docs/invoice.md) |

The obsolete legacy.py stub is removed. Its HELLO.cbl sample is preserved in
examples/pipeline-hello.cbl, outside discovery, so legacy/ contains exactly the
three actual demo programs. All P2 binary paths come from compile_cobol; compiled
Mac executables are not committed. [Detailed handoff](docs/final-handoff.md).
