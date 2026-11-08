# Handoff: where things stand (Nov 8, ~01:00 CST; deadline 10:00 AM)

> To continue on any computer, paste this file into Claude Code or Codex, opened in a fresh
> HackUTD checkout.

## Setup

```bash
git clone https://github.com/pranavcheedalla/HackUTD.git && cd HackUTD && git checkout main
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-backend.lock     # needs: brew install gnucobol
cp .env.example .env    # then put NVIDIA_API_KEY=nvapi-... in .env (needed for live runs only)
python tools/serve.py   # open http://127.0.0.1:8765
```

You don't need anything for recordings only: `cd web && python3 -m http.server 8765`.

## What's done (all on `main`)

- **Backend:** the full pipeline (spec → test inputs → real COBOL answer key → rewrite → verify → retry → accept).
  - Multi-file codebases (CALL, copybooks, dependency order, blocking).
  - Anti-cheat gate.
  - Per-attempt history.
  - Retries see the explanation agent's "why".
  - 361 tests: `python -m pytest -q tests dev/p4`.
- **Codebases:** `samples/legacy` ("Invoicing", 3 programs) and `samples/bank` ("Retail bank", 5 programs, 2 shared subprograms).
  `demo/retail-bank.zip` is the bank, ready to drop on stage.
- **Frontend (`web/`):**
  - case file (TSB 2018 and New Jersey 2020, with sources) → intake (Run live / Watch recording / drop a zip);
  - the galaxy replay narrates itself (one sentence and one proof per station);
  - click a ring for the caption, `DETAILS →` for the station readout (all 7 stations built by the team);
  - live mode follows a real run, with Switch to recording and Back to live;
  - `#live=<session>` follows a run started from the terminal.
- **Recordings** (`web/replays/`):
  - `codebase` (Invoicing; discount 27/30 → 30/30);
  - `bank` (5/5; ALERTS printed nothing on attempt 1, 0/20, then fixed);
  - `planted-bug` (12.34 vs 12.35, a controlled mutation).
- **Deck:** https://claude.ai/artifact/Ap61TUyjZMWmSy9TSfNut7 (7 slides with speaker notes).

## Demo script (about 3 minutes)

1. **Case file (30 s):** "Hard to change, and dangerous to change without proof."
2. Drop demo/retail-bank.zip; it plays the recorded real run. Say: 'this replays a real run from tonight; live takes about 25 minutes.'
3. **Let the bank recording play at 1× (adjust speed if needed):**
   - the ALERTS mismatch, caught and fixed;
   - then click the Verify ring → `DETAILS`.
4. **Optional: Run live instead.** Starts a real run of the uploaded codebase; allow about 25 minutes.

   If a program fails live, that's the point: "it won't ship code that's off by a cent, and it blocks everything that depends on it."

## Open items

1. **Untested:** one fresh live bank run, to check that the "why"-in-retries change helps.
   - An earlier live run failed ACCRUE three times on rounding vs truncation and blocked STATEMNT.
   - Takes about 25 minutes.
   - If it passes 5/5, consider re-exporting it as the bank recording:
     ```bash
     python tools/export_replay.py runs/sessions/<s> --name bank --title "Retail bank · 5 programs" --codebase samples/bank
     ```
2. **Rehearse the script once,** with a timer.
3. **Record the demo video** of the same flow. Recordings come out identical every take.
4. **Submit** by 10:00 AM.

## Where the details are

| What | Where |
|---|---|
| Galaxy usage | `web/README.md` |
| Station UI rules | `docs/station-prompts/COMMON.md` |
| Caption copy | `web/captions.js` |
| Server | `tools/serve.py` |
| Exporter | `tools/export_replay.py` |
