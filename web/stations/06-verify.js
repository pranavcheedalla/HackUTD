/* 06 — Verify. Owner: Madhav. Brief: docs/station-prompts/madhav.md
 * Starter view only: replace the body of render() (and add overlay()) following the brief. */
Stations.register(6, {
  agent: 'referee',
  render({ module, H }) {
    return H.list((module.history || []).map(a => `Attempt ${a.attempt}: ${a.passed} / ${a.total} match`));
  },
});
