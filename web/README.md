# Galaxy view

The demo frontend. Each COBOL program is a star that travels left to right through the
pipeline: Discover → Read → Probe → Record → Rewrite → Verify → Verified. The scene is black
and white while the code is old COBOL, and the northern lights come in as it becomes
verified Python. When Verify finds a mismatch, the real failing case and Nemotron's
explanation appear above the ring, and the star goes back to Rewrite.

Everything on screen is replayed from a recorded run. The page makes no model calls and
needs no network, so it plays the same way every time.

## Run it

```bash
cd web && python -m http.server 8765
```

Then open <http://127.0.0.1:8765>. Pick a replay in the bottom-left menu, or open one
directly with `#codebase` or `#planted-bug`.

| Key | Action |
|---|---|
| Space | Pause or play |
| R | Restart |
| ← → | Jump 3 seconds |
| Esc | Close the panel |

Click any star to open its COBOL, Python, spec, answer key, and attempts.

## Add a replay

```bash
python tools/export_replay.py runs/sessions/<session> --name codebase --title "Multi-file codebase"
python tools/export_replay.py runs/sessions/<session>-mutation --mutation --name planted-bug
```

This writes `web/replays/<name>.json` and lists it in `web/replays/index.json`. The export
drops absolute paths and API keys.

Runs made after the attempt-history change keep each failed case and its explanation. Older
runs show counts only.
