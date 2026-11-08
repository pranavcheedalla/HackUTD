/* 06 — Verify. Owner: Madhav. Brief: docs/station-prompts/madhav.md
 * The original program is the judge: every recorded COBOL output against the rewrite's. */
Stations.register(6, {
  agent: 'referee',

  render({ module, H }) {
    const history = module.history || [];
    if (!history.length) return H.empty('No verification was recorded for this program.');
    const last = history[history.length - 1], first = history[0];
    const firstFail = (first.total || 0) - (first.passed || 0);
    const verdict = v => (v === 'legacy_quirk' ? 'COBOL quirk' : 'new code bug');

    let html = H.stats([
      { value: `${last.passed} / ${last.total}`, label: 'final match', tone: last.passed === last.total ? 'ok' : 'bad' },
      { value: module.attempts || history.length, label: (module.attempts || history.length) === 1 ? 'attempt' : 'attempts' },
      { value: firstFail, label: 'wrong on attempt 1', tone: firstFail ? 'bad' : 'dim' },
    ]);
    html += H.text('Every recorded COBOL output is compared with the rewrite’s output, character for character. One difference sends it back.');

    history.forEach((a, i) => {
      const total = a.total || 0, passed = a.passed || 0, failed = Math.max(0, total - passed);
      const failures = a.failures || [];
      let body = H.dots([...Array(passed).fill('ok'), ...Array(failed).fill('bad')]);
      body += H.text(`${passed} of ${total} match.`);
      failures.slice(0, 3).forEach(f => { body += H.text(`Input ${f.input === '' ? '(empty)' : f.input}`) + H.diff(f.expected, f.actual); });
      if (a.explanation && a.explanation.reason) body += H.quote(a.explanation.reason, `Nemotron · ${verdict(a.explanation.verdict)}`);
      if (failed && !failures.length) body += H.empty('This run kept the counts only, not the failing cases.');
      if (failed && i < history.length - 1) body += H.text('Sent back to Rewrite with these cases.');
      html += H.section(`Attempt ${a.attempt || i + 1}`, body);
    });

    if (module.status === 'failed') html += H.section('Result', H.empty(`Not verified after ${module.attempts || history.length} attempts.`));
    else if (module.status !== 'done') html += H.section('Result', H.empty('The run is still working on this program.'));
    return html;
  },

  // one small dot per test in a ring around Verify, lighting up as the tests run
  overlay({ ctx, cx, cy, t, u, lc, attempt, clamp }) {
    if (!attempt || !attempt.total) return;
    const n = Math.min(attempt.total, 60), passed = Math.min(attempt.passed || 0, n);
    const lit = Math.floor(n * clamp(u / 0.45));
    for (let k = 0; k < n; k++) {
      const ang = -Math.PI / 2 + (k / n) * 2 * Math.PI, dx = cx + Math.cos(ang) * 40, dy = cy + Math.sin(ang) * 40;
      let col;
      if (k >= lit) col = `rgba(${lc},0.18)`;
      else if (k < passed) col = 'rgba(185,240,220,0.75)';
      else col = `rgba(255,170,195,${0.55 + 0.25 * Math.sin(t * 9 + k)})`;
      ctx.fillStyle = col; ctx.beginPath(); ctx.arc(dx, dy, 1.3, 0, Math.PI * 2); ctx.fill();
      if (k === lit - 1 && lit < n) {
        ctx.strokeStyle = k < passed ? 'rgba(185,240,220,0.5)' : 'rgba(255,170,195,0.5)';
        ctx.lineWidth = 0.6; ctx.beginPath(); ctx.arc(dx, dy, 3, 0, Math.PI * 2); ctx.stroke();
      }
    }
  },
});
