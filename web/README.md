# Galaxy view

The demo frontend. Each COBOL program is a star that travels left to right through the
pipeline: Discover → Read → Probe → Record → Rewrite → Verify → Verified. The scene is black
and white while the code is old COBOL, and the northern lights come in as it becomes
verified Python. When Verify finds a mismatch, the real failing case and Nemotron's
explanation appear above the ring, and the star goes back to Rewrite.

Everything on screen is replayed from a recorded run. The page makes no model calls and
needs no network, so it plays the same way every time.

## Run it

Dropping a zip of a known codebase plays its recorded real run (demo mode). Run live instead starts a real run.

Recordings open paused at Discover. Use **Next → / ← Back** or the keyboard arrows: the star travels along the path to the adjacent station, then pauses automatically, including at failed checks and retries. Stars and readouts remain interactive. **Pause** can stop a flight; **Auto-play** is optional and uses the speed selector. Restart returns to paused Discover.

**With live runs (recommended):**

```bash
python tools/serve.py          # then open http://127.0.0.1:8765
```

The page opens on the intake screen.

- **Run live** starts a real Nemotron run on that codebase, and the galaxy follows it as it happens.
- **Watch recording** plays a saved real run.
- **Dropping a .zip of COBOL** replays a known codebase, or starts a live run for a new codebase.

If live isn't possible (no `NVIDIA_API_KEY` in `.env`, or a run already in progress), the page
says so. During a live run, **Switch to recording** jumps to the saved run of the same codebase.

To follow a run started from the terminal (`tools/isolated_run.py`), open
`http://127.0.0.1:8765/#live=<session>`. A late join catches up at double speed.

**Recordings only, no server needed:**

```bash
cd web && python3 -m http.server 8765
```

Open a recording directly with `#codebase`, `#bank` or `#planted-bug`.

| Key | Action |
|---|---|
| Space | Pause or play |
| R | Restart |
| ← → | Previous / next station; remain paused |
| Esc | Close the panel |

## Add a replay

```bash
python tools/export_replay.py runs/sessions/<session> --name codebase --title "Multi-file codebase"
python tools/export_replay.py runs/sessions/<session>-mutation --mutation --name planted-bug
```

This writes `web/replays/<name>.json` and lists it in `web/replays/index.json`. The export
drops absolute paths and API keys.

Runs made after the attempt-history change keep each failed case and its explanation. Older
runs show counts only.
