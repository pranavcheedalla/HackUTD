# Frontend: what's done and what's next

> To continue on another computer, paste this whole file into your AI coding assistant,
> opened in a HackUTD checkout.

## Setup (2 minutes)

```bash
git clone https://github.com/pranavcheedalla/HackUTD.git && cd HackUTD
git fetch origin && git checkout person2/attempt-history   # or main, once PR #3 is merged
cd web && python3 -m http.server 8765                      # open http://127.0.0.1:8765
```

You don't need a Python environment, an API key, or COBOL to work on the frontend. The page
replays saved runs from `web/replays/*.json`.

## What exists (PR #3)

- `web/index.html`: the page shell, the controls (bottom left), and the side panel.
- `web/galaxy.js`: everything else. One canvas, no libraries. Sections, in order:
  - helpers;
  - static layers (milky way, fog, stars, grain);
  - `buildTimeline()`, which turns a replay into timed "beats": intro, move, dwell, swoop, outro;
  - drawing (`star()`, `drawAurora()`, `filament()`, `annotation()` for the mismatch note);
  - `draw(t)`, the frame;
  - the side panel (`openPanel`, `renderTab`);
  - loading.
- `tools/export_replay.py`: turns a backend session folder into a replay JSON. Each replay
  module has `id, file, kind, depends_on, status, attempts, tests_passed, tests_total,
  history[{attempt, passed, total, failures[{input, expected, actual}], explanation{verdict, reason, input}}],
  spec, cobol, python, golden[{input, output}], unit_tests_quarantined`.
- Debug hook in the browser console: `galaxy.seek(25)` jumps to 25 s and renders.
  `galaxy.beats` lists the timeline.

### Design rules (keep these)

- The main screen stays calm. Details appear only on click or for a moment, never as permanent clutter.
- Black and white means old COBOL. Purple and teal northern lights mean verified Python.
  The colour amount is `cs` (0 to 1).
- Text is small monospace capitals with letter spacing (`txt(...)`). No boxes or cards on the canvas.
- Everything shown comes from the replay data. Never hard-code fake values.

## Next tasks, in priority order

Push after each one: `git add -A web && git commit -m "..." && git push`.

### 1. Click a station ring to open that step's real output (about 45 min)

In `draw()`, push each station ring into `hits` with an id like `'st:3'`. In the click handler,
`'st:N'` opens the panel in a station mode for the current module. Optionally, ease the camera
toward the ring and pause the replay while the panel is open. Content per station:

| Station | Show |
|---|---|
| 01 Discover | The program list with kind (`subprogram`), `depends_on` as `invoice → discount`, and the file names |
| 02 Read | `spec.summary`, `business_rules`, `edge_cases`, `quirks` |
| 03 Probe | The `golden[].input` list (the generated test inputs) |
| 04 Record | A `golden` table: input → real COBOL output, titled "recorded from the actual COBOL program" |
| 05 Rewrite | COBOL and Python side by side (two `<pre>` columns) |
| 06 Verify | One row per `history` entry: `passed/total`, the failed cases (input, COBOL, rewrite), the explanation |
| 07 Verified | `tests_passed/tests_total`, `attempts`, `unit_tests_quarantined` |

### 2. A 30-dot test grid at Verify (about 45 min)

While a star dwells at station 5, draw `total` tiny dots in a ring or arc around the Verify ring.
They light up one by one over the first ~45% of the dwell. The first `passed` dots glow (teal
once colour is in); failing ones flash pink. Clicking a pink dot opens Verify's panel on that case.

### 3. Rewrite attempt diff (needs a small backend change)

The backend overwrites `modern/<id>.py` on each attempt. To show what changed, save each attempt's
source into the history entry in `pipeline/graph.py` (`rewrite` node, for example
`state["attempt_sources"]`, which must also be declared in `GraphState`, or LangGraph drops it).
Then export it in `tools/export_replay.py` and show a simple line diff in the Rewrite panel.

## Demo replays

- `#codebase`: a real Nemotron run. Discount was 27/30, then 30/30 on attempt 2 (counts only;
  the run predates the history change).
- `#planted-bug`: invoice, 12.34 vs 12.35, with Nemotron's real explanation. Labelled as a
  controlled mutation.

To add a new run with full mismatch detail, use any run made on this branch or later. On the
machine with the backend set up:

```bash
python tools/isolated_run.py --mode real --legacy-dir samples/legacy
python tools/export_replay.py runs/sessions/<new-session> --name codebase --title "Multi-file codebase"
```

## Check before pushing

```bash
node --check web/galaxy.js
```

Then reload the page, run `galaxy.seek()` through a few moments, and check the console has no errors.
