/* 03 — Probe. Owner: Pranav. Brief: docs/station-prompts/pranav.md
 * Starter view only: replace the body of render() following the brief. */
Stations.register(3, {
  agent: 'Nemotron',
  render({ module, H }) {
    const inputs = (module.golden || []).map(g => g.input);
    return H.section(`${inputs.length} test inputs`, H.list(inputs.map(s => s === '' ? '(empty)' : s)));
  },
});
