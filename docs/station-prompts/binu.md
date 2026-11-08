# Prompt for Binu (Abhinav): station 05 Rewrite + saving each attempt's code

> Paste everything below into your AI coding assistant (Claude Code or Codex), opened in your
> HackUTD checkout.

---

You are working on **Legacy → Verified**, a HackUTD project: NVIDIA Nemotron agents migrate
COBOL to Python and accept a rewrite only when every output matches the real COBOL. The
frontend in `web/` is a cinematic galaxy where each program is a star travelling through 7
stations. Clicking a station ring opens a side panel with that step's real output.

**Your task has two parts:**
1. **Backend:** a small change so the pipeline keeps **each attempt's Python**. Today it
   overwrites `modern/<id>.py` on every retry, so "what changed between attempt 1 and 2" is lost.
2. **Frontend:** the panel for **station 05 Rewrite**: COBOL next to Python, what changed between
   attempts, and why it was sent back.

You have one station because it's the richest and it includes the backend part.

## Step 0: read the shared rules (required)

Read `docs/station-prompts/COMMON.md` in full before writing code. It has the setup, the API,
the helper list, the data format, and the **UI rules you must follow exactly**. The rules exist
so all 7 stations look like one product.

In short:
- Only use the `H.*` helpers.
- No styles or colours.
- Real data only.
- Stats first, then sections.
- Sentence-case labels.
- Guard missing data.

Setup: follow COMMON.md, then create branch `stations/binu`. The backend part needs the Python
environment:

```bash
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-backend.lock   # needs: brew install gnucobol
```

## Your files

| File | What |
|---|---|
| `pipeline/graph.py` | **Only** the `GraphState` class and the `rewrite` node |
| `tests/pipeline/test_attempt_sources.py` | New file, your tests |
| `web/stations/05-rewrite.js` | Your station |

Edit nothing else. The exporter (`tools/export_replay.py`) already passes `attempt_sources`
through to the replay, so don't change it.

## Part 1: backend, keep every attempt's Python

In `pipeline/graph.py`:

1. Add to `class GraphState`:
   ```python
   attempt_sources: list    # [{attempt, python}] each rewrite's source, kept for the replay
   ```
   **This is required.** LangGraph silently drops state keys that aren't declared in `GraphState`.
2. In the `rewrite` node, after `src` is produced and the `attempts` value is computed, add the new
   entry to the state you return:
   ```python
   "attempt_sources": [*(state.get("attempt_sources") or []),
                       {"attempt": attempts, "python": src[:20000]}],
   ```
   Put it in the `out = {**state, ...}` dict. Don't change anything else in the node. The early
   "blocked" return stays as it is.
3. Tests in `tests/pipeline/test_attempt_sources.py`. Copy the fixture style from
   `tests/pipeline/test_attempt_history.py` (it patches `status.STATE_PATH`), and patch
   `graph.MODERN_DIR`, `graph.testing.golden_to_pytest` and `graph.agents.rewrite`. Assert:
   - two calls to `graph.rewrite(...)` (feeding the first result's state into the second) give
     `attempt_sources` with attempts `[1, 2]` and the two different sources;
   - `"attempt_sources" in graph.GraphState.__annotations__`;
   - a 30,000-character source is stored cut to 20,000.
4. Run the suite. Everything must stay green:
   ```bash
   python -m pytest -q tests dev/p4
   LLM_MODE=fake python tools/isolated_run.py --mode fake    # offline demo must still say 3/3
   ```
   Then check the newest session's `runs/state.json`: the `invoice` module should have two entries
   in `attempt_sources`, because the offline demo fails invoice once on purpose.
5. Optional, for a richer replay. Export that offline run and look at your station with real
   attempt diffs:
   ```bash
   python tools/export_replay.py runs/sessions/<newest fake session> --name offline-demo --title "Offline demo · invoice repairs"
   ```
   Don't commit `web/replays/*`: Madhav owns the demo replays. Keep this one local, or tell
   Madhav to add it.

## Part 2: station 05 Rewrite, "COBOL becomes Python"

Return `{ tabs: [...] }` with up to three tabs, in this order.

**Tab "Side by side"** (always):
1. **`H.stats`**:
   - `{ value: module.attempts, label: module.attempts === 1 ? 'attempt' : 'attempts' }`
   - `{ value: <COBOL line count>, label: 'COBOL lines', tone: 'dim' }`
   - `{ value: <Python line count>, label: 'Python lines' }`
2. If `module.depends_on` is non-empty, add **`H.section('Reuses verified code', ...)`**:
   - `H.text('Calls ' + deps + ' by importing the already-verified Python instead of rewriting it.')`
   - Then `H.code(module.python, { highlight })` limited with `from`/`to` to the lines around the
     `import <dep>` line and the first `<dep>.call(` line (about 4 lines of context each).
3. **`H.columns(cobolHtml, pythonHtml, ['COBOL', 'Python'])`**:
   - Left: `H.code(module.cobol, { highlight: cobolLogicLines })`. Logic lines are non-comment lines
     matching `/\b(IF|EVALUATE|WHEN|COMPUTE|MOVE|ADD|SUBTRACT|MULTIPLY|DIVIDE|PERFORM|CALL)\b/i`.
     Comments are lines whose 7th character is `*`, or that start with `*>`.
   - Right: `H.code(module.python, { highlight: pyLines })`, highlighting the `def main` and
     `def call` lines and lines containing `ROUND_` or `quantize`. Those are where COBOL's
     rounding and truncation rules live.
   - If either source is empty: `H.empty('Source not in this replay.')` in that column.

**Tab "Changes"** (only when `module.attempt_sources.length >= 2`):
- For each consecutive pair (attempt k → k+1), add
  `H.section('Attempt ' + k + ' → ' + (k + 1), H.table(['', 'Line'], rows, { tone }))`.
- Compute `rows` with a simple line diff:
  - Implement a small LCS on the two arrays of lines. They're a few hundred lines, so O(n·m) is fine.
  - Show only changed lines, plus 1 unchanged line of context around each change.
  - Removed lines are `['−', line]` with tone `'bad'`; added lines are `['+', line]` with tone `'ok'`;
    context lines are `['', line]` with no tone.
  - At most 40 rows per pair, with `H.text('Showing the first 40 changed lines.')` if cut.
- Before the table, add `H.text('What the agent changed after seeing the failing cases.')`.
- If the tab can't be built: `attempt_sources.length === 1` means show the tab only if you want to
  say "Passed on the first attempt", otherwise omit it. If it's empty (older replays such as
  `#codebase` and `#planted-bug`), **omit the tab entirely**.

**Tab "Sent back"** (only when some `module.history` entry has `passed < total`):
- For each such attempt, add `H.section('Attempt ' + a.attempt + ' · ' + a.passed + ' / ' + a.total, ...)`
  containing:
  - for each of up to 3 `a.failures`: `H.text('Input ' + f.input)` then `H.diff(f.expected, f.actual)`;
  - if `a.explanation && a.explanation.reason`:
    `H.quote(a.explanation.reason, 'Nemotron · ' + (a.explanation.verdict || '').replace('_', ' '))`;
  - if there are no failure details (older runs keep counts only):
    `H.empty('This run kept the counts only, not the failing cases.')`.

## Optional canvas overlay

Not needed. The galaxy already shows Python faintly behind Rewrite.

## Check

1. **Backend:** `python -m pytest -q tests dev/p4` is all green, and the offline demo shows 3/3.
2. **Frontend:** follow the checks in COMMON.md on **both** replays.
   - `#planted-bug`: press **5**. You should see "Side by side" and "Sent back". "Sent back" shows
     `TOTAL=00012.34` vs `TOTAL=00012.35` with only the last digit lit, plus Nemotron's sentence.
     There's no "Changes" tab, because that replay predates your backend change.
   - `#codebase`: press **5** on invoice. You should see the "Reuses verified code" section showing
     `import discount`. Discount's "Sent back" should show the calm "counts only" line.
   - If you exported `offline-demo` in part 1, open it and check the "Changes" tab.
3. No console errors. The panel matches the other stations' look.

## Push

```bash
node --check web/stations/05-rewrite.js
git add pipeline/graph.py tests/pipeline/test_attempt_sources.py web/stations/05-rewrite.js
git commit -m "Station 05 Rewrite: side by side, attempt changes, sent-back reasons; keep each attempt's source"
git push -u origin stations/binu
```

Push the backend part as soon as its tests pass, then the station. Tell Hemant your branch is ready.
