# Adversarial review and fixes

## Reproduced before fixing

Five of the first six attack regressions failed on the previous release:

1. A str subclass could return the wrong characters while its __eq__ always
   returned True. Fix: compare the built-in string value and independently check
   the captured result against the reporter's collection-time golden snapshot.
2. Editing generated expected values while retaining the golden-hash comment
   could pass. Fix: an additional manifest pins the entire generated test, and
   verification rechecks references/tests/manifest after the subprocess exits.
3. PYTEST_PLUGINS in the shell could break an otherwise valid run. Fix: isolated
   Python startup, explicit pytest configuration/plugin, no inherited plugin
   list/options, disabled conftest discovery and third-party autoload.
4. Duplicate JSON keys were silently accepted. Fix: strict object-pair parsing;
   impossible UTF-8 cases and malformed structured reports are rejected too.
5. A changed helper with identical size and timestamp loaded stale pyc and
   falsely passed. Fix: a fresh private helper cache with bytecode writes disabled.

These are regression-tested, including expected-value mutation during a call
and during rewrite import. The reporter freezes reference values before imports.

## Additional boundaries tested

- stdout/stderr floods fail with bounded memory instead of filling capture RAM.
  pytest capture is disabled in the worker so floods cannot hide in its temp files.
- Nonblocking pipe multiplexing handles large stdin alongside both output streams.
- Timeouts clean ordinary process groups, including children holding output pipes.
- COB_* runtime settings are cleared; ambient DISPLAY redirection cannot turn
  original output into an empty golden response. Runtime defaults are intentional.
- A binary changed during recording cannot replace an earlier golden reference.
- A golden file changed during verification cannot mark the new snapshot passed.
- Smoke --output cannot overwrite project source, inputs, or goldens: in-project
  reports must be under runs/ or validation/.
- Malformed/missing manifests, malformed counts/failures, invalid Unicode, path
  tricks in module-ID string subclasses, and unknown result cases fail closed.
- 600 seeded insert/delete mutation trials compare original output with independent
  Decimal fixtures, in addition to 532 targeted/grid/seeded arithmetic comparisons.

## Actual team graph compatibility

The audit discovered Hemant's new branch and tested its real contract.py,
pipeline/graph.py, and pipeline/status.py in a disposable overlay. The real P2
implementations replace his stubs. The legacy.py stub was removed and HELLO.cbl
relocated outside legacy/; P1 files on his remote branch were not modified.

The graph passed all-three acceptance, invoice repair on attempt 2, exhaustion
on attempt 3 routed to an explanation fixture, empty-input failure, and output
flood failure. Persisted module state agrees with final graph state. All agents
were deterministic fixtures, so no live-model spec/rewrite/explanation is claimed.
`tools/check_team_pipeline.py` reproduces these checks given a disposable merged
checkout and an environment with LangGraph (tested 1.2.20). The archive includes
the pinned graph commit, source hashes, scenarios, and outcomes in validation/.

## Limits

This is a local correctness/resource audit, not an OS security boundary. A
same-user program can access the filesystem and interpreter internals. The
listed hardening stops the tested false-pass and resource attacks; it does not
promise containment of arbitrary hostile code. Live Nemotron and final dashboard
checks remain explicit unchecked items in ACCEPTANCE_CHECKLIST.md.
