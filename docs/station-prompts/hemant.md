# Prompt for Hemant: station 01 Discover + station 02 Read

> Paste everything below into your AI coding assistant (Claude Code or Codex), opened in your
> HackUTD checkout.

---

You are working on **Legacy → Verified**, a HackUTD project: NVIDIA Nemotron agents migrate
COBOL to Python and accept a rewrite only when every output matches the real COBOL. The
frontend in `web/` is a cinematic galaxy where each program is a star travelling through 7
stations. Clicking a station ring opens a side panel with that step's real output.

**Your task: build the panels for station 01 Discover and station 02 Read.**

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

Setup: follow COMMON.md, then create branch `stations/hemant`.

## Your files

- `web/stations/01-discover.js`
- `web/stations/02-read.js`

Edit nothing else.

Both files already contain a small working starter. Replace the body of `render()`; keep the
`Stations.register(...)` call and the `agent` label.

## Station 01 Discover: "what is this codebase?"

This station shows the **whole codebase** the run migrated, not only the program on screen.
Use `replay.modules`; use `module` only to mark which program is on screen.

Build `render({ module, replay, H })` to return, in this order:

1. **`H.stats`** with three numbers:
   - `{ value: replay.modules.length, label: 'programs' }`
   - `{ value: <count of kind === 'subprogram'>, label: 'subprograms' }`
   - `{ value: <total number of depends_on links across all modules>, label: 'calls' }`
2. **`H.section('Call chain', …)`**:
   - For every module with a non-empty `depends_on`, add one `H.chain([...deps uppercased, module.id uppercased])`,
     e.g. `DISCOUNT ──→ INVOICE`. Join several chains with `''`.
   - If no module calls another: `H.empty('No program calls another.')`.
3. **`H.section('Programs', H.table([...]))`**:
   - Headers: `['File', 'Kind', 'Calls', 'Result']`.
   - One row per module:
     - `m.file`;
     - `m.kind`;
     - `m.depends_on.join(', ')` or `'—'`;
     - result: `'verified'` if `status === 'done'`, otherwise the plain error text, or `'not verified'`.
   - Row tone: `'ok'` if done, `'bad'` if not.
   - In the File cell of the row where `m.id === module.id`, show
     `H.raw(H.esc(m.file) + ' ' + H.tag('on screen', 'accent'))`.
4. **`H.section('Migration order', …)`**:
   - `H.list(replay.modules.map(m => m.id.toUpperCase()), true)`, a numbered list, in the order given.
   - Then `H.text('Programs are migrated callees first, so a caller can reuse code that is already verified.')`.
5. **`H.section('Shared copybooks', …)`**:
   - Scan each `m.cobol` for `COPY <NAME>` with
     `/^\s*COPY\s+["']?([A-Z0-9-]+)/gim`, skipping fixed-format comment lines where column 7 is `*`.
   - Build `name → [files that use it]`.
   - Show `H.kv([[name, files.join(', ')], ...])`, or `H.empty('No shared copybooks.')`.

No tabs for Discover.

## Station 02 Read: "what Nemotron understood"

This station shows the **spec Nemotron wrote** for the program on screen (`module.spec`).

Return `{ tabs: [ { label: 'Spec', html }, { label: 'Source', html } ] }`.

**Tab "Spec"**, in order:
1. **`H.stats`**: `{ value: rules.length, label: 'business rules' }`,
   `{ value: edge_cases.length, label: 'edge cases' }`, `{ value: quirks.length, label: 'COBOL quirks' }`.
2. **`H.section('Summary', H.text(spec.summary))`**.
3. **`H.section('Business rules', H.list(spec.business_rules, true))`**, numbered.
4. **`H.section('Inputs', H.table(['Name', 'Type', 'Format'], spec.inputs.map(i => [i.name, i.type, i.format])))`**,
   only when `spec.inputs` has entries. Same for **Outputs**.
5. **`H.section('Edge cases', H.list(spec.edge_cases))`**.
6. **`H.section('COBOL quirks', …)`**: a list, or `H.empty('None noted.')`.
   Quirks matter most to judges (for example, truncation instead of rounding), so don't drop this section.

**Tab "Source":**
- `H.code(module.cobol, { highlight })`, where `highlight` holds the 1-based line numbers of the
  lines that carry logic: lines matching `/\b(IF|ELSE|EVALUATE|WHEN|COMPUTE|MOVE|ADD|SUBTRACT|MULTIPLY|DIVIDE|PERFORM|CALL)\b/i`
  that are not comments. Comments are lines whose 7th character is `*`, or that start with `*>`.
- Above it, add `H.text('Highlighted lines are the logic the spec describes.')`.

If `module.spec` is missing or empty, the Spec tab shows `H.empty('No spec was recorded for this program.')`.
Never throw.

## Optional canvas overlay

None for your stations. Read already shows the spec rules faintly in the scene.

## Check

Follow the checks in COMMON.md on **both** replays:
- On `#codebase`, press **1** and check the chain shows `DISCOUNT ──→ INVOICE` and the copybook
  `INVREC` lists `invoice.cbl`. Press **2** while each of the 3 programs is on screen
  (use `galaxy.seek(…)`; `galaxy.beats` shows when each program is active).
- On `#planted-bug`, press **1** (one program, no calls) and **2**.
- The console must show no errors. The panels must look like the other stations: same fonts, spacing, labels.

## Push

```bash
node --check web/stations/01-discover.js && node --check web/stations/02-read.js
git add web/stations/01-discover.js web/stations/02-read.js
git commit -m "Stations 01 Discover and 02 Read: codebase map and Nemotron's spec"
git push -u origin stations/hemant
```

Push after each station, not only at the end. You're also the merger: when teammates' branches
are pushed, merge `stations/*` into the integration branch one by one. They touch different
files, so expect no conflicts. Then reload and press 1–7 on both replays.
