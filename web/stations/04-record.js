/* 04 — Record. Owner: Pranav. Brief: docs/station-prompts/pranav.md
 * Starter view only: replace the body of render() following the brief. */
Stations.register(4, {
  agent: 'real COBOL',
  render({ module, H }) {
    const rows = (module.golden || []).map(g => [g.input, g.output]);
    return H.section('Answer key', H.table(['Input', 'COBOL output'], rows));
  },
});
