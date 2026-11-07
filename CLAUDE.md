# Project context for Claude Code

## What we're building
A multi-agent system using NVIDIA Nemotron models that reads a legacy codebase (like COBOL), writes plain-English specs of what it does, records its real outputs as tests, rewrites it module by module into modern code (Python), and only accepts each rewrite once it produces exactly the same outputs as the original.

Hackathon project. Deadline: Sunday Nov 8, 10:00 AM Central. Team of 4.

## My role (Hemant, Person 1): pipeline lead + only person who merges
- `contract.py`: shared types and function signatures. Don't change signatures without telling the team.
- `llm.py`: `call_llm("nano"|"super", system, user, json_schema=None)` via `langchain-nvidia-ai-endpoints`. Retries, JSON repair, disk cache in `.cache/llm`. `LLM_MODE=fake` for stub runs. Model IDs come from `.env` (verify on build.nvidia.com).
- `pipeline/graph.py`: LangGraph loop per module: extract_spec -> record -> rewrite -> verify -> accept, with verify routing back to rewrite (failures fed back, max `MAX_ATTEMPTS`=3), then explain -> failed.
- `pipeline/status.py`: atomically writes `runs/state.json` after every node (dashboard reads it).
- `run.py`: `python run.py [legacy_dir] [--only id]`; runs `agents.understand` first to order modules.

## Teammates (their files are STUBS until merged; each has `STUB = True`)
- P2 `legacy.py`, `testing.py`, `legacy/*.cbl`: GnuCOBOL compile/run, golden recording to `golden/<id>.jsonl`, golden->pytest, `run_equivalence(module_id) -> {passed,total,failures}`.
- P3 `agents/understanding.py`: `understand`, `extract_spec` (Nano), `generate_inputs` (Super).
- P4 `agents/building.py`: `rewrite` (Super), `write_unit_tests`, `explain_divergence` -> `{verdict: new_code_bug|legacy_quirk, reason}`.

## Conventions
- COBOL programs read ONE line from stdin (ACCEPT) and DISPLAY output. No files/DBs.
- Rewritten modules live at `modern/<id>.py` and expose `def main(input_line: str) -> str`.
- Money uses `decimal.Decimal`. Every LLM call goes through `llm.call_llm`.

## Merge schedule (Central time)
- 2:00 PM contract + stubs pushed (done)
- 2:30 PM P2 pushes COBOL program #1 + golden outputs
- 5:00 PM Merge 1: real functions replace stubs, run each phase on program #1
- 8:00 PM Merge 2: full pipeline on program #1, no manual steps (go/no-go)
- 11:30 PM Merge 3: all 3 programs incl. truncation-quirk program, then frontend (Streamlit reading runs/state.json) on one computer
- 8:30 AM feature freeze, 9:30 AM submit

## Status
- Stub pipeline verified: `LLM_MODE=fake python run.py` passes (retry path and explain path both tested).
- Next for me: real Nemotron smoke test (`python llm.py`), then merges.
