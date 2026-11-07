# Person 2 resume checkpoint

Completed: segments 1–8. Next: segment 9 (payroll), then 10 (invoice).

- GnuCOBOL 3.2.0, Python 3.11.15, pytest 9.2.0 installed and verified on this Mac.
- Runtime helpers, hello-world checker, 99-line interest program, 15 inputs,
  and 15 real golden outputs complete.
- Runtime review covers process-group cleanup, exact stdout, atomic recording,
  source-name collisions, locale, portable paths, and golden drift checks.
- Equivalence generator and structured pytest runner complete, with unchanged
  signatures and fresh-process execution. Generated tests precede the rewrite.
- Independent Decimal audit includes 132 additional COBOL calculations.
- Tests cover the original cases, matching/broken rewrites, formatting differences,
  missing imports, rapid edits, stale golden data, skipped cases, and timeouts.

Repository: https://github.com/pranavcheedalla/HackUTD
Branch: person2/legacy-runtime-harness
PR: https://github.com/pranavcheedalla/HackUTD/pull/1

The first delivery (segments 1–4) is a separate commit from the equivalence
harness (segments 5–8). Hemant retains merge ownership. No NVIDIA credentials
were needed. Tests and validation reports are in this package. The development
virtual environment is the enclosing workspace's work/.venv.

Before starting segments 9–10, use an updated screenshot to check allowance;
the old usage screenshot does not provide live remaining usage.
