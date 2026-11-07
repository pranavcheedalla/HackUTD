# Combined P1 + P2 integration

This branch merges Hemant's `hemant/pipeline-skeleton` at ee58f2f with the P2
runtime/harness at e4aa781, preserving both Git histories for review.

## Resolved integration points

- Keep the real legacy/ package and remove P1's obsolete legacy.py stub.
- Keep the hardened testing.py and testing_reporter.py, including manifests.
- Preserve the placeholder HELLO source in examples/pipeline-hello.cbl so it does
  not become a fourth demo module.
- Combine ignore rules: secrets, live state, generated code/tests/specs, and caches.
- Keep contract.py, llm.py, and graph routing unchanged from Hemant's branch.
- Add only an explicit fixture-mode selector to run.py and a mode label to the
  state writer. P3/P4 functions and every shared signature are preserved.
- Root README now covers the combined backend. P2's full earlier runtime guide is
  preserved at docs/person2-runtime.md.

## Verified workflows

`LLM_MODE=fake python run.py` runs actual GnuCOBOL, actual LangGraph, and actual
pytest equivalence. Agents are visibly labeled handwritten fixtures. All three
modules pass 15/15; invoice fails 2 cases first and repairs on attempt 2.

`LLM_MODE=fake python run.py --only invoice --demo-scenario exhaust` verifies
three attempts and then the explanation route, yielding 13/15 and two explicit
fixture explanations labeled legacy_quirk. The expected exit code is 2.

`python run.py` defaults to real mode and refuses remaining P3/P4 stubs before
writing state or calling a model. No fixture success is passed off as real output.
State JSON has mode=offline_fixture or mode=real_model for dashboard consumers.

The combined suite includes the 209 prior P2 tests, five public CLI integration
checks, and three mocked LLM cache/retry/repair checks. The model client checks
make no network calls. Tests use copies in directories containing spaces and
check that the 45 saved golden records stay identical.

## Reproduce

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-combined.lock
python -m pytest -q
LLM_MODE=fake python run.py
```

Run regression tests in a clean checkout before generating pipeline artifacts,
or account for additional generated pytest files. For the real-model run later,
install requirements.txt as well and configure the NVIDIA key/model IDs locally.
Never commit .env. The combined lock pins the tested offline environment and
includes LangGraph; the old requirements-dev.lock remains the P2-only profile.

## Remaining work, in template order

- Hemant reviews the combined PR and merges main. Both branch histories are already
  combined here; no stub-file cleanup remains for the P1/P2 merge.
- Review/integrate P3's actual understanding-agent branch abhinav/understand_agents.
- Integrate P4's real rewrite, unit-test, and explanation agents. At this fetch,
  Pranav still had only the initial README.
- Configure a real NVIDIA key and verify model IDs; run Hemant's llm.py smoke.
- Run program #1 with actual model agents, then all three. Check invoice divergence,
  retries, live state, and the final dashboard. Preserve baseline regression
  recordings by using a separate checkout/worktree for generated input sets.

The offline demo and mocked client tests do not verify live Nemotron behavior.
