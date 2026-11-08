/* 07 — Verified. Owner: Madhav. Brief: docs/station-prompts/madhav.md
 * Starter view only: replace the body of render() following the brief. */
Stations.register(7, {
  agent: 'accepted',
  render({ module, H }) {
    return module.status === 'done'
      ? H.stats([{ value: `${module.tests_passed} / ${module.tests_total}`, label: 'outputs match', tone: 'ok' }])
      : H.empty('Not verified.');
  },
});
