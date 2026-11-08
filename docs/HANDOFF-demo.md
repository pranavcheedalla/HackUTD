# NorthBase handoff (Nov 8; deadline 10:00 AM CST)

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

## What's implemented

The NorthBase intake and presenter controls are in PR #10, pending merge approval.
The established backend and recordings are on main.

- **Backend:** the full pipeline (spec → test inputs → real COBOL answer key → rewrite → verify → retry → accept).
  - Multi-file codebases (CALL, copybooks, dependency order, blocking).
  - Anti-cheat gate.
  - Per-attempt history.
  - Retries see the explanation agent's "why".
  - 366 tests: `python -m pytest -q tests dev/p4`.
- **Codebases:** `samples/legacy` ("Invoicing", 3 programs) and `samples/bank` ("Retail bank", 5 programs, 2 shared subprograms).
  `demo/retail-bank.zip` is the bank, ready to drop on stage.
- **Frontend (`web/`):**
  - NorthBase landing page opens by default, with a large wordmark slightly left of center and a shooting star in the same sky;
  - Read the case file opens TSB 2018 and New Jersey 2020, with sources; Home returns to the landing page from the story, replay, or Details;
  - a recognised zip zooms through the drop star into paused Discover; reduced motion skips the zoom;
  - black/silver legacy sky → violet rewrite → mint aurora after acceptance;
  - the galaxy replay narrates itself (one sentence and one proof per station);
  - captions have no background source text, program-name clutter, or duplicate corner metadata; the honest replay disclosure stays visible without a date;
  - click a ring for the caption, `DETAILS →` for the station readout (all 7 stations built by the team);
  - live mode follows a real run, with Switch to recording and Back to live;
  - `#live=<session>` follows a run started from the terminal.
- **Recordings** (`web/replays/`):
  - `codebase` (Invoicing; discount 27/30 → 30/30);
  - `bank` (5/5; ALERTS printed nothing on attempt 1, 0/20, then fixed);
  - `planted-bug` (12.34 vs 12.35, a controlled mutation).
- **Deck:** https://claude.ai/artifact/Ap61TUyjZMWmSy9TSfNut7 (7 slides with speaker notes).

## Demo script (about 3 minutes)

1. **Open NorthBase → Read the case file (30 s):** "Hard to change, and dangerous to change without proof." Click **Hand it the codebase →** to return to the landing page.
2. Drop demo/retail-bank.zip; the star entrance arrives paused at Discover in the recorded real run. Say: 'this replays a real run from tonight; live takes about 25 minutes.'
3. **Use Next → to fly between stations and pause at each one, starting at Discover:**
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
