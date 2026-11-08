# NorthBound: Claude continuation handoff

> **Update (PR after #10):** a dropped known zip no longer arrives paused. After the entrance it
> replays the recorded run **as a run**: `startSim()` in `web/galaxy.js` feeds the recording's real
> events one at a time into `liveTimeline()`, each step "working" for its real duration compressed
> 12× (1.4–3.6 s, `REAL RUN · mm:ss` in the caption), then the result lands. Next skips a wait;
> Restart replays it; Pause/Back work. Direct recording links (`#bank` etc.) keep the paused
> presenter mode. Tests: `tests/pipeline/test_sim_replay.py`.

Repository: https://github.com/pranavcheedalla/HackUTD

Continue from `main`. PR #9 added demo-on-drop; PR #10 contains the NorthBound design,
presenter controls, star entrance, caption cleanup, and Home navigation described below.
The user authorized merging PR #10 into main. Preserve teammates' local work and `.env`;
inspect `git status` before switching branches or pulling. Do not reset their checkout.

## Read first

- `docs/HANDOFF-demo.md`: full project setup, stage script, and remaining backend work.
- `web/README.md`: frontend usage and routes.
- `tools/serve.py`: local API, uploads, and known-codebase recording recognition.
- `web/galaxy.js`: playback, drawing, entrance, routing, uploads, and live runs.
- `web/index.html`: layout, styling, Home controls, and zip target.

## What changed in the recent session

1. **NorthBound landing:** `/` opens the landing page, ready for a zip. The large, heavy
   monospace wordmark sits slightly left of center on desktop, with responsive phone
   sizing. No visible codebase inventory or new cards. The existing black/silver galaxy
   includes a left-to-right shooting star. `#codebases` remains a landing alias.
2. **Case file:** Read the case file opens `#case` (TSB 2018 and New Jersey 2020, with
   sources). Home and Hand it the codebase return to the landing page.
3. **Known zip demo:** Drop `demo/retail-bank.zip`. The server returns `recording: "bank"`
   and the title. The recognition note shows for about 1.2 seconds; then a 1.5-second
   canvas entrance zooms through the drop star and docks at the first program's actual
   Discover position. Playback arrives paused at 1×. This uses a recorded real Nemotron
   run, with no new model calls. The upload API already matches known codebases.
4. **Presenter control:** Next/Back and arrow keys animate the star along the real station
   path, then pause automatically. The bank has 38 stops, including all modules, the
   ALERTS failure/retry, and the summary. Double clicks cannot skip stops. Pause can
   interrupt a flight; Back returns to its departure stop. Auto-play is optional.
5. **Home:** The replay toolbar starts with Home. The case file and Details panel also
   have Home controls, including on phones. Home cancels travel/entrance, pauses the
   view, closes readouts, resets landing scroll, and focuses the wordmark. Delayed live
   start responses and fallback timers cannot pull the user away after Home. Restart
   resets the current replay to paused Discover; it is distinct from Home.
6. **Clean captions:** Kept the explanation, proof, and Details link. Removed decorative
   background source text, program names, duplicate corner file/status headers, replay
   date, and repeated help text. Compact captions suppress surrounding program clusters
   so stars and connecting lines cannot sit behind their words. Full evidence remains
   available in Details. The honest `REPLAY OF A REAL NEMOTRON RUN` disclosure stays.
7. **Color progression:** Black/silver legacy sky, violet during rewriting, mint aurora
   after acceptance. Mint is gated on acceptance rather than just progress.
8. **Responsive/accessibility work:** Case file and intake scroll in short windows;
   Details scrolls within its panel. Footer wraps above the toolbar. Escape cancels an
   entrance safely. Reduced motion skips the entrance and intake comet.
9. **Live behavior:** Unknown zips still request a real run. Run live instead explicitly
   starts a real run on the uploaded codebase. Switch to recording / Back to live and
   `#live=<session>` remain supported. Recording links (`#bank`, `#codebase`,
   `#planted-bug`) still open directly, paused at Discover.

## Run and rehearse

Use the existing Python environment if present. For a fresh environment, follow
`docs/HANDOFF-demo.md` (Python 3.11, requirements-backend.lock, GnuCOBOL).

```bash
python tools/serve.py
```

Open http://127.0.0.1:8765/ . A rehearsal server may already be running on this Mac at
http://127.0.0.1:8766/ from the `work/demo-drop` worktree; do not assume another computer
can reach that localhost URL. A fresh Claude checkout should start its own server.

Stage flow: NorthBound landing → Read the case file → Hand it the codebase → drop
`demo/retail-bank.zip` → recognition → star entrance → paused Discover → Next/Back.
Keep the replay disclosure honest. Explain that this replays a real run and that a live
run takes about 7 minutes (One program live: about 25 s). Home is available to return to the beginning.

No NVIDIA key is needed for the recorded demo. Use `tools/serve.py` for zip uploads;
`python -m http.server` supports direct recording playback but has no upload API.
Do not commit, print, or paste API keys. A new checkout needs local NVIDIA configuration
only for live runs.

## Validation already completed

```bash
node --check web/galaxy.js
python -m pytest -q tests dev/p4
git diff --check
```

All **366 tests passed**. Frontend tests cover presenter travel, all bank retry stops,
comet timing, entrance docking/cancellation/reduced motion, mint-after-acceptance,
default routing, Home handlers, direct links, and stale live-start/fallback responses.

Browser checks covered desktop/phone/short landscape layouts, real scrolling, zip
recognition and entrance, paused arrival, Back/Next, Escape, caption cleanup, Details,
fresh default landing, Home during a flight, and Home from mobile Details in Chrome.
The in-app demo console had no errors. Chrome automated file selection was blocked by
the extension's file-URL permission; upload was verified in the in-app browser. No
browser permission settings were changed.

Recent work changed the UI and navigation; it did not make fresh model calls or prove
that a new live bank run passes. Existing recordings are real-run evidence. The full
handoff still lists a fresh live bank run, rehearsal, video recording, and submission
as remaining tasks. Keep the current visual language and presenter-led interaction.
