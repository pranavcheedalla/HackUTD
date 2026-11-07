# P3 understanding agents: merge notes for Hemant

## Copy into the repo
| File | Goes to | Notes |
|---|---|---|
| `agents/understand.py` | `agents/` | `understand(legacy_dir)`, plus `load_cobol_source(cobol_path)` |
| `agents/extract_spec.py` | `agents/` | `extract_spec(cobol_src)` (Nano) |
| `agents/generate_inputs.py` | `agents/` | `generate_inputs(spec, cobol_src)` (Super) |
| `agents/cobol_static.py` | `agents/` | regex/PIC parser used by all three (no LLM) |
| `agents/_llm.py`, `agents/_json.py` | `agents/` | `_llm` picks up `llm.call_llm` automatically once it exists |
| `agents/__init__.py` | merge | add the 3 import lines into yours |
| `tests/unit/test_understanding_agents.py`, `tests/fake_llm.py` | `tests/` | offline, no API key |
| `eval_understanding.py` | repo root | `python eval_understanding.py legacy/` |
| `llm_local.py` | **do not copy** | temporary stand-in for `llm.call_llm` |

## Pipeline wiring (please do this)
1. **Pass expanded source to the agents:** `src = load_cobol_source(module["cobol_path"])`,
   then `extract_spec(src)` / `generate_inputs(spec, src)`. Without it, copybook fields are invisible.
2. **Overwrite the module id:** `spec["module_id"] = module["module_id"]`. extract_spec only sees
   source, so it uses PROGRAM-ID lowercased.
3. **module_id = file stem, lowercased, non-alphanumerics -> `_`** (`pay-roll.cbl` -> `pay_roll`), so
   `modern/<id>.py` is importable.
4. **Modules with no ACCEPT** (CALLed subprograms) can't be run from stdin. Skip record/verify for
   them, or test them through their caller.
5. understand() adds extra keys per module: `program_id`, `copybooks`, `unresolved_calls`. They're safe to ignore.

## Behaviour worth knowing
- extract_spec validates against the Spec schema and retries once with the errors. If it's still
  bad, it fills gaps from the parser instead of crashing.
- If the parser proves a COMPUTE/MULTIPLY/DIVIDE stores into a field **without ROUNDED** and the
  model didn't list it, a `[static check, line N] ...` quirk is appended. This keeps the truncation
  catch in the demo from depending on the model.
- generate_inputs asks once more if it gets fewer than 20 cases, caps them at 30, and adds all-zeros/all-nines
  baselines for numeric-only records. Why each input exists is in `agents.generate_inputs.LAST_RUN`.

## Needs
`langchain-nvidia-ai-endpoints`, `python-dotenv` (only for llm_local), `pytest`. Stdlib otherwise.
