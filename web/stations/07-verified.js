/* 07 — Verified. Owner: Madhav. Brief: docs/station-prompts/madhav.md
 * What "verified" means for this program, with the evidence behind it. */
Stations.register(7, {
  agent: 'accepted',

  render({ module, H }) {
    if (module.status !== 'done') {
      return H.empty('This program was not verified.') + (module.error ? H.text(module.error) : '');
    }
    const attempts = module.attempts || (module.history || []).length || 1;
    const heldout = module.heldout, deps = (module.depends_on || []).map(d => d.toUpperCase()).join(', ');

    const stats = [{ value: `${module.tests_passed} / ${module.tests_total}`, label: 'recorded outputs match', tone: 'ok' }];
    if (heldout && heldout.total) stats.push({ value: `${heldout.passed} / ${heldout.total}`, label: 'unseen inputs match', tone: heldout.passed === heldout.total ? 'ok' : 'bad' });
    stats.push({ value: attempts, label: attempts === 1 ? 'attempt' : 'attempts' });
    let html = H.stats(stats);

    const means = ['Every recorded output matches the real COBOL, character for character.'];
    if (heldout && heldout.total) means.push(`Checked again on ${heldout.total} inputs it never saw: ${heldout.passed} match.`);
    means.push('The rewrite computes its answers. Code that reads files or the answer key is rejected.');
    if (deps) means.push(`Reuses the verified ${deps} instead of rewriting it.`);
    html += H.section('What verified means', H.list(means));

    let tests;
    if (module.unit_tests_status === 'passed') {
      tests = H.tag('passed', 'ok') + H.text('Nemotron also wrote unit tests for the new code, and they pass.');
    } else if (module.unit_tests_status === 'needs_review') {
      tests = H.tag('needs review', 'bad')
        + H.text('Nemotron also wrote unit tests. These disagreed with the verified code and are kept, skipped, for a person to check:')
        + ((module.unit_tests_quarantined || []).length ? H.list(module.unit_tests_quarantined) : H.empty('The names of the skipped tests were not recorded.'));
    } else {
      tests = H.empty('No generated unit tests in this replay.');
    }
    html += H.section('Generated unit tests', tests);

    const py = String(module.python || ''), lines = py ? py.replace(/\s+$/, '').split('\n').length : 0;
    html += H.section('Final Python', py
      ? H.code(py, { to: 40 }) + (lines > 40 ? H.text(`Showing the first 40 of ${lines} lines.`) : '')
      : H.empty('The final Python is not in this replay.'));
    return html;
  },
});
