/* 02 — Read. Owner: Hemant. Brief: docs/station-prompts/hemant.md
 * Starter view only: replace the body of render() following the brief. */
Stations.register(2, {
  agent: 'Nemotron',
  render({ module, H }) {
    const spec = module.spec || {};
    return spec.summary ? H.section('Summary', H.text(spec.summary)) : H.empty('No spec recorded for this program.');
  },
});
