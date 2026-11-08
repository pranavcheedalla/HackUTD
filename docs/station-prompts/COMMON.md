# Station views: rules for everyone (read this first, it's required)

Every person's prompt points here. These rules are what make the 7 station views look like
one product. Breaking them breaks the demo.

## What we're building

**Legacy → Verified** (HackUTD, 8090 × NVIDIA Nemotron). NVIDIA Nemotron agents migrate old
COBOL to Python. A rewrite is accepted only when every output matches the real COBOL program,
character for character.

The frontend in `web/` is a cinematic "galaxy". Each COBOL program is a star travelling left to
right through 7 stations:

```
01 Discover → 02 Read → 03 Probe → 04 Record → 05 Rewrite ⇄ 06 Verify → 07 Verified
```

The scene is black and white while the code is old COBOL. Purple and teal northern lights come in
as it becomes verified Python. It replays **recorded real runs** from `web/replays/*.json`, with no
AI calls and no network.

**Your job:** when someone clicks a station ring (or presses its number key 1–7), a panel
slides in from the right showing **what that step really produced** for the program on screen.
The framework (panel, camera, styles, building blocks) is already done. You fill in the content
of your station file(s).

## Setup (5 minutes)

```bash
git clone https://github.com/pranavcheedalla/HackUTD.git   # or, if you already have it: cd HackUTD && git fetch origin
cd HackUTD
git checkout main
git pull
git checkout -b stations/<your-name>        # e.g. stations/hemant
cd web && python3 -m http.server 8765       # leave this running
```

Open <http://127.0.0.1:8765> in Chrome.

- Keys **1–7** open each station. **Esc** closes the panel, **Space** pauses or plays,
  **← →** jump 3 seconds.
- Switch replays in the bottom-left menu, or with `#codebase` and `#planted-bug` in the URL.
- After saving a file, reload the page (Cmd+Shift+R).
- In the console, `galaxy.seek(30)` jumps to 30 s, and `galaxy.beats` lists the timeline.

You don't need Python packages, an API key, or COBOL for frontend work.

## Files

| You may edit | Never edit |
|---|---|
| Only your own `web/stations/0N-*.js` file(s) (and the backend files your prompt names) | `web/galaxy.js`, `web/index.html` (the styles), `web/stations/registry.js`, other people's station files, `web/replays/*` |

If you think the framework needs a change, ask Madhav rather than editing it. That keeps
everyone's UI identical and merges conflict-free.

## The API

```js
Stations.register(N, {
  agent: 'Nemotron',                      // small label in the panel header
  render({ module, replay, H }) {         // return an HTML string, or { tabs: [{ label, html }, ...] }
    return H.stats([...]) + H.section('Business rules', H.list(rules, true));
  },
  overlay(api) { /* optional: canvas drawing at your ring, only if your prompt asks for it */ },
});
```

- `module` is the program on screen (the active star). `replay.modules` is every program in the run.
- The panel header (`06 — Verify`, then the file name and kind) is drawn for you. Don't repeat it.

## UI rules (MUST)

1. **Build panels only from `H.*` helpers.** No inline `style=`, no `<style>`, no new CSS
   classes, no colours, no emoji, no icons, no images. If a helper can't do it, simplify the
   idea. Don't add a helper.
2. **Layout order:**
   - **H.stats** first (1–3 big numbers), if your station has numbers;
   - then **H.section** blocks, most important first;
   - **tabs** only when your prompt says so. At most 3 tabs, labels 1–2 words, sentence case.
3. **Words:**
   - Section labels: sentence case, 1–3 words ("Business rules", not "BUSINESS RULES:").
     The CSS styles them as spaced caps.
   - No exclamation marks, no "successfully", no marketing words.
   - Plain, short, factual.
4. **Real data only.** Every number and line comes from `module` or `replay`. When data is
   missing, show `H.empty('…one plain sentence…')`. Never invent, pad, or hard-code values.
   Never hide a failure.
5. **Keep it short:**
   - Lists and tables show at most 40 rows. When you cut, add
     `H.text('Showing the first 40 of 52.')`.
   - Code: use `H.code(src, { from, to })` for long files.
6. **Never crash.** Treat every field as possibly missing (`module.spec || {}`,
   `module.history || []`). A thrown error shows a plain message instead of your view, so guard
   it yourself.
7. **Canvas overlays** (only if your prompt includes one):
   - Draw only within ~90 px of your ring (`api.cx`, `api.cy`), never above `api.cy - 110`.
     The mismatch note lives there.
   - Thin lines (`lineWidth` ≤ 1), small dots (radius ≤ 1.6), alpha ≤ 0.8. No filled shapes
     bigger than a dot, no boxes, no gradients.
   - Colours only from this palette, as `'r,g,b'` strings:
     - `api.lc`: the scene's line colour; grey that turns lavender;
     - white `'232,234,242'`;
     - teal (pass) `'185,240,220'`;
     - pink (fail) `'255,170,195'`;
     - violet `'200,180,255'`.
   - Text only through `api.txt(str, x, y, size 9–12, alpha, letterSpacing 2–3)`, in SPACED CAPS.
   - Keep it subtle. It should look like it was always part of the galaxy.

## Helper reference (`web/stations/registry.js`)

| Helper | Use it for |
|---|---|
| `H.stats([{ value, label, tone }])` | Big thin numbers. `tone`: `'ok'` (teal), `'bad'` (pink), `'dim'` |
| `H.section(label, html)` | A titled block |
| `H.text(str)` / `H.empty(str)` | A sentence / a muted "missing data" sentence |
| `H.list(items, numbered?)` | Bullets. Items are text, or `H.raw(html)` |
| `H.table(headers, rows, { tone: i => 'ok' \| 'bad' \| '' })` | Rows of text, or `H.raw(html)` cells. `''` shows as "(empty)" |
| `H.kv([[key, value], ...])` | Label → value pairs |
| `H.code(src, { highlight: [lineNumbers], from, to })` | Source with line numbers. Highlighted lines glow violet |
| `H.columns(leftHtml, rightHtml, [labelL, labelR])` | Two columns side by side |
| `H.diff(expected, actual, ['COBOL', 'Rewrite'])` | Only the differing characters are lit. The same look as the canvas |
| `H.quote(text, by)` | Nemotron's words, e.g. `H.quote(reason, 'Nemotron · new code bug')` |
| `H.chain(['DISCOUNT', 'INVOICE'])` | DISCOUNT ──→ INVOICE |
| `H.dots(['ok', 'ok', 'bad', ...])` | One small dot per test |
| `H.tag(text, tone)` | A small label. tone: `'ok'`, `'bad'`, `'dim'`, `'accent'` |
| `H.raw(html)` | Wrap helper output to put inside `H.table` cells, `H.kv` values, or `H.list` items |

## Data reference (one entry of `replay.modules`)

```js
{
  id: 'invoice', file: 'invoice.cbl', program_id: 'INVOICE',
  kind: 'program' | 'subprogram', depends_on: ['discount'],     // programs this one CALLs
  status: 'done' | 'failed', error: null | 'blocked: dependency discount not verified',
  attempts: 2, tests_passed: 30, tests_total: 30,
  history: [ { attempt: 1, passed: 26, total: 30,
               failures: [ { input: '1|12.35|0.01', expected: 'TOTAL=00012.34', actual: 'TOTAL=00012.35' } ],
               explanation: { verdict: 'new_code_bug' | 'legacy_quirk', reason: '…', input: '…' } | null },
             { attempt: 2, passed: 30, total: 30, failures: [], explanation: null } ],
  spec: { summary, business_rules: [str], edge_cases: [str], quirks: [str],
          inputs: [{ name, type, format }], outputs: [{ name, type, format }] },
  cobol: '…full COBOL source…', python: '…final verified Python…',
  golden: [ { input, output }, ... ],          // the answer key recorded from the real COBOL (up to 40)
  attempt_sources: [ { attempt, python } ],    // each attempt's Python (newer runs only; may be [])
  heldout: { passed: 200, total: 200 } | null, // extra unseen inputs checked against the real COBOL
  unit_tests_status: 'passed' | 'needs_review' | 'fixture', unit_tests_quarantined: ['test_x'],
}
```

The two demo replays are worth knowing:
- `#codebase` has 3 programs. Discount failed 27/30 and then passed 30/30, but the failing
  cases were not saved, so `failures` is `[]` there.
- `#planted-bug` has 1 program (invoice) with the full failure detail.

**Test on both.**

## Checks before you push

```bash
node --check web/stations/0N-yourfile.js        # for each file you changed
```

1. Reload the page on **both** replays. Press your number keys.
2. Check the panel reads well, matches the other stations' look, and the console shows no errors.
3. Check a station on a program where data is missing (for example discount's failures on `#codebase`):
   it must show a calm `H.empty(...)` line, not a crash.

## Push (after each finished station, not only at the end)

```bash
git add web/stations/0N-yourfile.js            # only your files
git commit -m "Station 0N <name>: <what it shows>"
git push -u origin stations/<your-name>
```

Then tell Hemant your branch is ready. Each branch touches different files, so merges are conflict-free.
