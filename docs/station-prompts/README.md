# Station views: who does what

Each person pastes **their** prompt into their AI coding assistant. Every prompt starts by
having the assistant read [`COMMON.md`](COMMON.md), so all 7 panels follow the same UI rules.

| Person | Stations | Prompt |
|---|---|---|
| Hemant | 01 Discover, 02 Read | [`hemant.md`](hemant.md) |
| Pranav | 03 Probe, 04 Record | [`pranav.md`](pranav.md) |
| Binu (Abhinav) | 05 Rewrite, plus the backend change that keeps each attempt's code | [`binu.md`](binu.md) |
| Madhav | 06 Verify (panel and test-dot overlay), 07 Verified | [`madhav.md`](madhav.md) |

**Why this stays identical and conflict-free:**
- The panel, camera, styles and building blocks are shared and frozen
  (`web/galaxy.js`, `web/index.html`, `web/stations/registry.js`).
- Each person edits only their own `web/stations/0N-*.js` file(s). Binu also edits the
  `rewrite` node in `pipeline/graph.py`.
- Every station already has a working starter, so the page works at every step.

**Merge (Hemant):** merge each `stations/<name>` branch into the integration branch. Then open the
page, press 1–7 on both `#codebase` and `#planted-bug`, and check the console has no errors.
