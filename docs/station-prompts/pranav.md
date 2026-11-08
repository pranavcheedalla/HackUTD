# Prompt for Pranav: station 03 Probe + station 04 Record

> Paste everything below into your AI coding assistant (Claude Code or Codex), opened in your
> HackUTD checkout.

---

You are working on **Legacy → Verified**, a HackUTD project: NVIDIA Nemotron agents migrate
COBOL to Python and accept a rewrite only when every output matches the real COBOL. The
frontend in `web/` is a cinematic galaxy where each program is a star travelling through 7
stations. Clicking a station ring opens a side panel with that step's real output.

**Your task: build the panels for station 03 Probe and station 04 Record.** Together they tell
the "answer key" story: Nemotron invents test inputs, then we run the **real COBOL** on them and
save exactly what it prints. That saved output is what every rewrite is judged against.

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

Setup: follow COMMON.md, then create branch `stations/pranav`.

## Your files

- `web/stations/03-probe.js`
- `web/stations/04-record.js`

Edit nothing else.

Each file has a small working starter. Replace the body of `render()`; keep `Stations.register(...)`
and the `agent` label.

## Station 03 Probe: "how we try to break it"

The test inputs are the `input` side of `module.golden` (`[{ input, output }]`).

Return, in this order:

1. **`H.stats`**:
   - `{ value: inputs.length, label: 'test inputs' }`
   - `{ value: <number of groups that have at least one input>, label: 'kinds of case' }`
2. **Groups.** Put each input into the **first** group it matches, in this order, and show one
   `H.section(groupName, H.list(items))` per non-empty group, in this order:

   | Group | Rule (on the raw input string) |
   |---|---|
   | `Blank and empty` | `input.trim() === ''`, or any `|`-separated field is blank |
   | `Text and codes` | contains a letter `/[A-Za-z]/` |
   | `Maximums` | contains a run of four or more `9`s, e.g. `99999.99` |
   | `Zeros` | every numeric field is zero, e.g. `0`, `0.00`, `000` |
   | `Boundaries and typical` | everything else |

   - Show `''` as `(empty)` and a space-only string as `(spaces)`, so nothing looks missing.
   - Show at most 12 items per group. If you cut, end the list with a plain
     `H.text('…and 7 more.')` after it.
3. **`H.section('Why', H.text('Each input is chosen to hit a branch, a limit, or bad data, so the rewrite has to match the COBOL everywhere, not only on easy cases.'))`**.
4. If the replay contains failures (`module.history` entries with `failures`), add
   **`H.section('Caught the rewrite', H.list(...))`** listing the inputs that later exposed a
   mismatch (de-duplicated). This links Probe to Verify. If none, omit the section.

No tabs for Probe.

## Station 04 Record: "the answer key from the real COBOL"

Return `{ tabs: [ { label: 'Answer key', html }, { label: 'Source', html } ] }`.

**Tab "Answer key"**, in order:
1. **`H.stats`**:
   - `{ value: golden.length, label: 'answers recorded' }`
   - `{ value: <number of distinct outputs>, label: 'distinct outputs' }`
   - `{ value: 'GnuCOBOL', label: 'real compiler', tone: 'dim' }`
2. **`H.section('Recorded from the real program', H.table(['#', 'Input', 'COBOL output'], rows, { tone }))`**:
   - One row per golden case, at most 40, numbered from 1.
   - **Tone** `'bad'` for rows whose `input` appears in any `module.history[].failures[].input`.
     These are the exact cases the rewrite later got wrong.
   - After the table, if any rows are tinted, add
     `H.text('Tinted rows are the cases a rewrite later got wrong.')`.
   - If you cut at 40, add `H.text('Showing the first 40 of N.')`.
3. **`H.section('How it was recorded', H.kv([...]))`**:
   - `['Program', module.file]`
   - `['Compiler', 'GnuCOBOL (cobc)']`
   - `['Runs', 'one fresh process per input, 5 second limit']`
   - `['Kept', 'exactly what the program printed']`

   Those are the backend's real settings (`legacy/runtime.py`).

**Tab "Source":**
- `H.text('Highlighted lines print the outputs that were recorded.')`
- Then `H.code(module.cobol, { highlight })`, highlighting the 1-based line numbers of non-comment
  lines containing `DISPLAY` (or `GOBACK` for a subprogram, which has no DISPLAY).
  Comments are lines whose 7th character is `*`, or that start with `*>`.

If `module.golden` is empty, both stations show `H.empty('No answer key was recorded for this program.')`.

## Optional canvas overlay

None needed. The galaxy already orbits 30 probe dots at station 03.

## Check

Follow the checks in COMMON.md on **both** replays:
- `#planted-bug` (invoice): press **4**. The row `1|12.35|0.01 → TOTAL=00012.34` should be tinted,
  because it is a recorded failure. Press **3** and check the groups.
- `#codebase`: check all three programs (use `galaxy.seek(…)` and `galaxy.beats` to reach each).
  Discount is a subprogram: its inputs look like `G|1.00|1.00` and its outputs like
  `LK-TIER=G|LK-SUBTOTAL=…`.
- No console errors. The panels match the other stations' look.

## Push

```bash
node --check web/stations/03-probe.js && node --check web/stations/04-record.js
git add web/stations/03-probe.js web/stations/04-record.js
git commit -m "Stations 03 Probe and 04 Record: test inputs and the real COBOL answer key"
git push -u origin stations/pranav
```

Push after each station. Then tell Hemant your branch is ready.
