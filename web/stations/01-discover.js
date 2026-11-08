/* 01 — Discover. Owner: Hemant. Brief: docs/station-prompts/hemant.md
 * Starter view only: replace the body of render() following the brief. */
Stations.register(1, {
  agent: 'codebase scan',
  render({ replay, H }) {
    return H.section('Programs', H.list(replay.modules.map(m => `${m.file} · ${m.kind}`)));
  },
});
