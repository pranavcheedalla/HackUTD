# Person 2 acceptance checklist

Checked items below have executable evidence. Pending team actions are left
unchecked. This checklist does not certify arbitrary Python as safe to execute.

## Twelve build segments

- [x] **1. Mac setup:** Python 3.11, GnuCOBOL, isolated environment, reproducible hello-world check (`check_setup.py`).
- [x] **2. Compile/run:** subprocess execution, exact successful stdout, separate stderr, timeouts, child cleanup, and compilation diagnostics (`tests/runtime/test_runtime.py`).
- [x] **3. Interest:** 99-line original and 15 handwritten ordinary/zero/negative/maximum cases.
- [x] **4. Record:** actual executable outputs in `golden/interest.jsonl`; atomic replacement, executable fingerprint, no Python-generated oracle values.
- [x] **5. Generate pytest:** delayed rewrite import, exact string assertions, duplicate-case IDs, generated-file integrity manifest.
- [x] **6. Run equivalence:** real pytest subprocess, structured counts/diffs, validated report schema, no successful empty/skipped/partial run.
- [x] **7. Prove failure detection:** correct fixtures pass; arithmetic, formatting, exceptions, and rounding mutations fail (`tests/harness/`, program tests).
- [x] **8. Harden retries/infrastructure:** stale entry/helper bytecode, modified tests, hostile string equality, reference mutation, output floods, environment contamination, malformed goldens/reports (`tests/adversarial/`).
- [x] **9. Payroll:** 104-line original, 15 inputs/goldens, overtime and fictional tax boundaries, independent Decimal audit.
- [x] **10. Invoice:** 101-line original, 15 inputs/goldens, real PIC 9(5)V99 truncation, explicit integer overflow, demonstrated 13/15 rounding mutation and 15/15 repair.
- [x] **11. Contract and graph integration:** all five parameter lists and actual contract shapes match. Hemant's graph at `origin/hemant/pipeline-skeleton` was exercised in an isolated overlay using agent fixtures: accept, repair, exhaustion/explanation route, empty input, output flood. State persistence checked (`validation/team-integration.json` in the archive).
- [x] **12. Handoff:** documentation, version lock, 45 actual golden records, repeatable smoke, archive hashes, and full suite after actual ZIP extraction.

## Explicit requirement checks

- [x] Exactly three demo originals under legacy/; hello-world outside discovery.
- [x] Every original is under 150 lines, reads one line, and DISPLAYs without file/database I/O.
- [x] Fifteen handwritten inputs per original: 45 distinct per-module input records total.
- [x] Ordinary, zero, negative, and maximum-field cases represented for every program.
- [x] All five named public functions implemented with the original parameter names.
- [x] Money arithmetic in Python fixtures uses Decimal.
- [x] Spaces, leading zeros, signs/errors, decimal places, Unicode, and output newlines are preserved or checked as documented.
- [x] Golden outputs recorded only from original executables; existing originals and references unchanged by hardening.
- [x] Wrong output cannot pass via overloaded equality, stale helper bytecode, or a modified generated file in the tested attacks.
- [x] Output capture is bounded at 2 MiB combined stdout/stderr; excess raises a failure rather than returning truncated output.
- [x] 532 additional Decimal comparisons and 600 seeded mutation trials exercise all three originals.
- [x] No NVIDIA keys/API calls required for component or fixture integration checks.

## Team actions still pending

- [x] Combine Hemant's branch with P2, remove the stub clash, relocate HELLO, and resolve README/.gitignore/testing.py conflicts (docs/combined-integration.md).
- [ ] Hemant reviews the combined PR #1 and merges main.
- [ ] Run actual P3/P4 agents via llm.call_llm and Nemotron; verify real specs, generated inputs, Python rewrites, and divergence explanations.
- [ ] Run the complete real-model pipeline and inspect its final state/dashboard before the demo.

The actual graph was tested with substituted agents, not live model outputs.
Those pending checks require their implementations and credentials. Passing a
finite test set is not a proof for all inputs or a security sandbox. Generated
code still executes with the account's filesystem privileges; use OS isolation
for genuinely untrusted programs. Hash manifests detect drift, not a same-user
attacker who can rewrite the harness and every integrity file together.

The combined branch now includes direct CLI and mocked LLM-wrapper checks. See
[combined integration](combined-integration.md) for current run modes and next steps.
