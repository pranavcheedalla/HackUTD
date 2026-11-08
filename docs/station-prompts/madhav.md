# Prompt for Madhav: station 06 Verify (with test-dot overlay) + station 07 Verified

> Paste everything below into your AI coding assistant (Claude Code or Codex), opened in your
> HackUTD checkout.

---

You are working on **Legacy → Verified**, a HackUTD project: NVIDIA Nemotron agents migrate
COBOL to Python and accept a rewrite only when every output matches the real COBOL. The
frontend in `web/` is a cinematic galaxy where each program is a star travelling through 7
stations. Clicking a station ring opens a side panel with that step's real output.

**Your task: build station 06 Verify (panel plus a canvas overlay of test dots) and station 07
Verified (panel).** Verify is the most important moment of the demo, because it's where the
original program judges the rewrite.

## Step 0: read the shared rules (required)

Read `docs/station-prompts/COMMON.md` in full before writing code. It has the setup, the API,
the helper list, the data format, and the **UI rules you must follow exactly**, including the
**canvas overlay rules** (palette, sizes, where you may draw). The rules exist so all 7 stations
look like one product.

Setup: follow COMMON.md, then create branch `stations/madhav`.

## Your files

- `web/stations/06-verify.js`
- `web/stations/07-verified.js`

Edit nothing else. You also own the demo replays in `web/replays/` if new ones need exporting;
use `tools/export_replay.py`.

## Station 06 Verify, panel: "the original program is the judge"

Return, in this order (no tabs):

1. **`H.stats`**:
   - `{ value: last.passed + ' / ' + last.total, label: 'final match', tone: last.passed === last.total ? 'ok' : 'bad' }`,
     where `last` is the last `module.history` entry;
   - `{ value: module.attempts, label: module.attempts === 1 ? 'attempt' : 'attempts' }`;
   - `{ value: firstFail, label: 'wrong on attempt 1', tone: firstFail ? 'bad' : 'dim' }`,
     where `firstFail = history[0].total - history[0].passed`.
2. **`H.text('Every recorded COBOL output is compared with the rewrite’s output, character for character. One difference sends it back.')`**
3. For **each** history entry, add `H.section('Attempt ' + a.attempt, ...)` containing:
   - `H.dots(states)`, where `states` has `a.passed` entries of `'ok'` followed by
     `a.total - a.passed` entries of `'bad'`. The run keeps counts, not the order, so passes go first.
   - `H.text(a.passed + ' of ' + a.total + ' match.')`
   - For up to 3 of `a.failures`: `H.text('Input ' + f.input)` then `H.diff(f.expected, f.actual)`.
   - If `a.explanation && a.explanation.reason`:
     `H.quote(a.explanation.reason, 'Nemotron · ' + verdictWords)`, where `verdictWords` is
     `'new code bug'` or `'COBOL quirk'` for `legacy_quirk`.
   - If `a.passed < a.total` and `a.failures` is empty:
     `H.empty('This run kept the counts only, not the failing cases.')`.
   - If this attempt failed and a later one exists: `H.text('Sent back to Rewrite with these cases.')`.
4. If `module.status !== 'done'`: `H.section('Result', H.empty('Not verified after ' + module.attempts + ' attempts.'))`.

## Station 06 Verify, canvas overlay: the test dots

Add `overlay(api)` to the `Stations.register(6, {...})` object. It runs every frame while the star
dwells at Verify, and while the Verify panel is open. Draw **one small dot per test in a ring
around the Verify ring**, lighting up as the tests run.

```
api: { ctx, cx, cy, t, u, c, lc, module, attempt, focused, txt, clamp, mix, rgb, W, H }
  u        0→1 progress through the stop at Verify (1 when the panel is open)
  attempt  the history entry being verified right now: { passed, total, failures, ... }
  lc       the scene's line colour 'r,g,b' (grey → lavender as colour arrives)
```

Exact spec. Stay inside these numbers so it matches the scene:

- `n = attempt.total`, capped at 60. Positions are on a circle of radius **40** around
  `(api.cx, api.cy)`, starting at the top (angle −π/2) and going clockwise:
  `angle = -Math.PI / 2 + k / n * 2 * Math.PI`.
- **Lit count:** `lit = Math.floor(n * clamp(u / 0.45))`, so all dots light during the first 45%
  of the stop. That's when the counter under the ring counts up.
- Dot `k` is drawn as a circle of radius **1.3** (`ctx.arc`, `ctx.fill`):
  - not yet lit (`k >= lit`): `rgba(${lc}, 0.18)`;
  - lit and a pass (`k < attempt.passed`): teal `rgba(185,240,220, 0.75)`;
  - lit and a fail: pink `rgba(255,170,195, a)` with `a = 0.55 + 0.25 * Math.sin(t * 9 + k)` (a soft flicker).
- **Just-lit glow:** the most recently lit dot (`k === lit - 1`, while `lit < n`) also gets a ring
  of radius 3 (`ctx.arc`, `ctx.stroke`, `lineWidth 0.6`) in the same colour at alpha 0.5.
- Nothing else: no labels, no lines, no boxes. The counter text under the ring already exists.
- Guard: if `!attempt || !attempt.total`, return without drawing.
- It must not be drawn above `api.cy - 110`. Radius 40 is well inside that.

## Station 07 Verified, panel: "what verified means"

Return, in this order (no tabs):

1. If `module.status !== 'done'`: return `H.empty('This program was not verified.')` plus, if
   `module.error`, `H.text(module.error)`. Stop.
2. **`H.stats`**:
   - `{ value: module.tests_passed + ' / ' + module.tests_total, label: 'recorded outputs match', tone: 'ok' }`
   - if `module.heldout`: `{ value: heldout.passed + ' / ' + heldout.total, label: 'unseen inputs match', tone: heldout.passed === heldout.total ? 'ok' : 'bad' }`
   - `{ value: module.attempts, label: module.attempts === 1 ? 'attempt' : 'attempts' }`
3. **`H.section('What verified means', H.list([...]))`**, with these exact items, the second only
   when `heldout` exists:
   - `'Every recorded output matches the real COBOL, character for character.'`
   - `'Checked again on ' + heldout.total + ' inputs it never saw: ' + heldout.passed + ' match.'`
   - `'The rewrite computes its answers. Code that reads files or the answer key is rejected.'`
   - if `module.depends_on.length`: `'Reuses the verified ' + deps + ' instead of rewriting it.'`
4. **`H.section('Generated unit tests', ...)`**:
   - `unit_tests_status === 'passed'`: `H.tag('passed', 'ok')` plus `H.text('Nemotron also wrote unit tests for the new code, and they pass.')`
   - `'needs_review'`: `H.tag('needs review', 'bad')` plus
     `H.text('Nemotron also wrote unit tests. These disagreed with the verified code and are kept, skipped, for a person to check:')`
     plus `H.list(module.unit_tests_quarantined)`
   - otherwise: `H.empty('No generated unit tests in this replay.')`
5. **`H.section('Final Python', ...)`**:
   - `H.code(module.python, { to: 40 })`
   - `H.text('Showing the first 40 of N lines.')` when the file is longer.

No overlay for 07. The constellation already celebrates it.

## Check

Follow the checks in COMMON.md on **both** replays:
- `#planted-bug`:
  - Run the replay and watch Verify: 30 dots light around the ring, 4 pink on attempt 1, all
    teal on attempt 2.
  - Press **6**: attempt 1 shows `TOTAL=00012.34` / `TOTAL=00012.35` with only the last digit lit,
    and Nemotron's quote.
  - Press **7**: there's no held-out stat in this replay, and that's fine.
- `#codebase`:
  - Discount's Verify: 27/30 then 30/30, with the calm "counts only" line.
  - Press **7** on each program: held-out shows `200 / 200`.
  - Invoice's unit tests show "needs review" with `test_worked_examples_exact`.
- The dots must look like part of the galaxy: thin, small, subtle. If they draw the eye more than
  the star does, make them dimmer.
- No console errors.

## Push

```bash
node --check web/stations/06-verify.js && node --check web/stations/07-verified.js
git add web/stations/06-verify.js web/stations/07-verified.js
git commit -m "Stations 06 Verify and 07 Verified: test dots, per-attempt results, what verified means"
git push -u origin stations/madhav
```

Push after each station. Then tell Hemant your branch is ready.
