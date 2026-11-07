# Legacy Modernization Agents

A multi-agent system using NVIDIA Nemotron models that reads a legacy codebase (like COBOL), writes plain-English specs of what it does, records its real outputs as tests, rewrites it module by module into modern code, and only accepts each rewrite once it produces exactly the same outputs as the original.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env            # add your NVIDIA_API_KEY
LLM_MODE=fake python run.py     # runs end to end on stubs, no API needed
python llm.py                   # smoke-test the real Nemotron connection
```

## Who owns what (only Hemant merges)

| File | Owner | Replace the stub with |
| --- | --- | --- |
| `contract.py` | Hemant | Shared types + signatures. Don't change without telling Hemant. |
| `llm.py` | Hemant | Done: Nemotron client, retries, JSON repair, disk cache |
| `pipeline/`, `run.py` | Hemant | Done: LangGraph loop + `runs/state.json` writer |
| `legacy.py`, `testing.py`, `legacy/*.cbl` | P2 | GnuCOBOL compile/run, golden recording, pytest harness |
| `agents/understanding.py` | P3 | `understand`, `extract_spec`, `generate_inputs` |
| `agents/building.py` | P4 | `rewrite`, `write_unit_tests`, `explain_divergence` |

When your real code is ready, delete `STUB = True` from your file. `run.py` prints which pieces are still stubs.

## The loop (one module)

```
extract_spec -> record -> rewrite -> verify --pass--> accept (unit tests written) -> done
                             ^          |
                             +--retry---+  failures fed back, up to MAX_ATTEMPTS
                                        |
                                        +--still failing--> explain divergences -> failed
```

## Folders

```
legacy/            original .cbl files
specs/             <module>.json specs
golden/            <module>.jsonl recorded input/output pairs
modern/            rewritten .py files (each exposes main(input_line) -> str)
tests/equivalence/ generated from golden/
tests/unit/        written by the test agent
runs/state.json    live status the dashboard reads
```

## Rules
- Every LLM call goes through `llm.call_llm("nano" | "super", system, user, json_schema=None)`.
- COBOL programs read ONE line from stdin and DISPLAY output. No files or databases.
- Money uses `decimal.Decimal`.
