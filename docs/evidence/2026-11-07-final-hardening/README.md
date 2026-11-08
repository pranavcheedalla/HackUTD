# Final backend check and hardening (2026-11-07)

A full attack on the merged backend, then fresh real Nemotron runs with the model cache off
(`LLM_CACHE=0`), so every answer is a new model call.

## Fresh real runs on the final code

| Run | Order | Result | Held-out audit vs real COBOL |
|---|---|---|---|
| `20261107-193451-real-ec3c96` (`legacy/`) | interest → invoice → payroll | 3/3, 89/89, 1 attempt each | 926/926 (`heldout_audit_3_programs.json`) |
| `20261107-193920-real-09217f` (`samples/legacy`) | discount → interest → invoice | 3/3, 74/74; discount repaired on attempt 2 | 600/600 (200 per module, fuzzed fixture inputs) |

- `invoice.py` does `import discount` and calls `discount.call(...)`.
- All 6 rewrites pass the new self-containment check.
- Mutation check on the 3-program session:
  - the planted `ROUND_HALF_UP` bug fails 4/30 cases, including 12.34 vs 12.35;
  - Nemotron explains it as `new_code_bug`;
  - the repair passes 30/30 on attempt 1.

## Attacks (none crashed the pipeline)

**Hostile agents through the real graph and real COBOL (20 scenarios):**

| Agent | What it did |
|---|---|
| Model | Outage in every agent |
| Rewrite | Syntax errors, no `main` |
| Rewrite | Infinite loop, 10 MB output, `sys.exit`, `os._exit` at import |
| Rewrite | Non-str return, `None` source |
| Rewrite | **Reads the golden answer key** |
| Inputs | Empty, non-string, duplicate, multiline or NUL inputs |
| Spec | Not a dict |

**Bad folders:**
- missing, empty or random-byte folders;
- COBOL syntax errors and missing copybooks;
- CALL cycles (both modules blocked), self-CALL, dynamic CALL;
- unicode and duplicate file names.

**COBOL runtime:**
- a program that loops forever (stopped at 5 s);
- 2 MB+ output floods;
- non-zero exits;
- a 100k-character input and 2,000 inputs;
- path-traversal module ids;
- missing files.

**LLM wrapper:**
- invalid JSON (one repair attempt, then a clean error);
- an empty or think-only reply;
- 401 (no retry), 500 forever (gives up after 4 tries), 429 then OK;
- a corrupt or empty cache entry (regenerated).

## Fixes made

1. **Anti-cheat gate** (`testing.rewrite_violations`):
   - A rewrite may import only pure standard-library modules plus its verified dependencies, and may not use `open`, `exec`, `eval`, a dynamic `__import__`, or interpreter internals.
   - It's enforced in the rewrite agent's self-check, so the model is told and fixes its code, and as a hard gate in `verify`.
   - The `if __name__ == "__main__":` block and `__import__("re")` are allowed.
   - Before the fix, a rewrite that read `golden/*.jsonl` was "verified".
2. **Input cleanup** (`graph.clean_inputs`): non-string, multiline and duplicate inputs are dropped instead of failing the module.
3. **Minimum evidence:** a module is never accepted on fewer than `MIN_TESTS` (default 5) distinct cases.
4. **Unit-test quarantine:**
   - Model-written unit tests that still disagree with the COBOL-verified module after repair are kept in the file, marked `@pytest.mark.skip` with a reason, and listed in `unit_tests_quarantined`.
   - Passing tests are kept, and status stays `needs_review`.
   - Before, one bad assertion discarded the whole file.
5. **CLI:** a missing legacy folder and an unknown `--only` id print a message instead of a traceback.

## Tests

- `tests/pipeline/test_final_hardening.py` (25 tests).
- Full suite: 341 passed.
- `CODEBASE_MERGE=1 tests/codebase`: 23/23, 0 pending.
