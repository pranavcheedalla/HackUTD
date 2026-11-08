/* 05 — Rewrite. Owner: Binu (Abhinav). Brief: docs/station-prompts/binu.md */
Stations.register(5, {
  agent: 'Nemotron',
  render({ module, H }) {
    const m = module || {};
    const cobol = String(m.cobol || ''), python = String(m.python || '');
    const linesOf = src => src.replace(/\s+$/, '') ? src.replace(/\s+$/, '').split('\n') : [];
    const cobolLines = linesOf(cobol), pyLines = linesOf(python);
    const attempts = Number(m.attempts) || 0;

    // ---- Side by side ----
    let side = H.stats([
      { value: attempts, label: attempts === 1 ? 'attempt' : 'attempts' },
      { value: cobolLines.length, label: 'COBOL lines', tone: 'dim' },
      { value: pyLines.length, label: 'Python lines' },
    ]);

    const deps = (Array.isArray(m.depends_on) ? m.depends_on : []).filter(Boolean);
    if (deps.length) {
      const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const anchors = [];
      deps.forEach(d => {
        const imp = pyLines.findIndex(l => new RegExp('^\\s*(import\\s+' + esc(d) + '\\b|from\\s+' + esc(d) + '\\s+import\\b)').test(l));
        const call = pyLines.findIndex(l => l.includes(d + '.call('));
        if (imp >= 0) anchors.push(imp + 1);
        if (call >= 0) anchors.push(call + 1);
      });
      anchors.sort((a, b) => a - b);
      const windows = [];
      anchors.forEach(n => {
        const from = Math.max(1, n - 4), to = Math.min(pyLines.length, n + 4), last = windows[windows.length - 1];
        if (last && from <= last.to + 1) last.to = Math.max(last.to, to);
        else windows.push({ from, to });
      });
      const code = windows.length
        ? windows.map(w => H.code(python, { highlight: anchors, from: w.from, to: w.to })).join('')
        : H.empty('The import is not in this replay.');
      side += H.section('Reuses verified code',
        H.text('Calls ' + deps.join(', ') + ' by importing the already-verified Python instead of rewriting it.') + code);
    }

    const logic = /\b(IF|EVALUATE|WHEN|COMPUTE|MOVE|ADD|SUBTRACT|MULTIPLY|DIVIDE|PERFORM|CALL)\b/i;
    const isComment = l => l.charAt(6) === '*' || l.trimStart().startsWith('*>');
    const cobolHi = [], pyHi = [];
    cobolLines.forEach((l, i) => { if (!isComment(l) && logic.test(l)) cobolHi.push(i + 1); });
    pyLines.forEach((l, i) => { if (/^\s*def\s+(main|call)\b/.test(l) || /ROUND_|quantize/.test(l)) pyHi.push(i + 1); });
    side += H.columns(
      cobolLines.length ? H.code(cobol, { highlight: cobolHi }) : H.empty('Source not in this replay.'),
      pyLines.length ? H.code(python, { highlight: pyHi }) : H.empty('Source not in this replay.'),
      ['COBOL', 'Python']);

    const tabs = [{ label: 'Side by side', html: side }];

    // ---- Changes ----
    const sources = (Array.isArray(m.attempt_sources) ? m.attempt_sources : [])
      .filter(s => s && typeof s.python === 'string')
      .slice().sort((a, b) => (a.attempt || 0) - (b.attempt || 0));
    if (sources.length >= 2) {
      let html = '';
      for (let p = 0; p + 1 < sources.length; p++) {
        const a = linesOf(sources[p].python), b = linesOf(sources[p + 1].python);
        // LCS table, then walk it into a list of [op, line]
        const n = a.length, k = b.length, dp = Array.from({ length: n + 1 }, () => new Int32Array(k + 1));
        for (let i = n - 1; i >= 0; i--) for (let j = k - 1; j >= 0; j--)
          dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
        const ops = [];
        let i = 0, j = 0;
        while (i < n || j < k) {
          if (i < n && j < k && a[i] === b[j]) { ops.push(['', a[i]]); i++; j++; }
          else if (i < n && (j >= k || dp[i + 1][j] >= dp[i][j + 1])) { ops.push(['−', a[i]]); i++; }
          else { ops.push(['+', b[j]]); j++; }
        }
        const keep = new Set();
        ops.forEach((o, x) => { if (o[0]) { keep.add(x); if (x > 0) keep.add(x - 1); if (x + 1 < ops.length) keep.add(x + 1); } });
        const rows = ops.filter((o, x) => keep.has(x));
        // H.table prints '' as "(empty)"; a space keeps the marker cell and blank code lines blank
        const shown = rows.slice(0, 40).map(o => [o[0] || ' ', o[1] || ' ']);
        const from = sources[p].attempt || p + 1, to = sources[p + 1].attempt || p + 2;
        html += H.text('What the agent changed after seeing the failing cases.') +
          H.section('Attempt ' + from + ' → ' + to, shown.length
            ? H.table(['', 'Line'], shown, { tone: x => shown[x][0] === '−' ? 'bad' : shown[x][0] === '+' ? 'ok' : '' }) +
              (rows.length > 40 ? H.text('Showing the first 40 changed lines.') : '')
            : H.empty('The code did not change between these attempts.'));
      }
      tabs.push({ label: 'Changes', html });
    }

    // ---- Sent back ----
    const sentBack = (Array.isArray(m.history) ? m.history : [])
      .filter(a => a && typeof a.passed === 'number' && typeof a.total === 'number' && a.passed < a.total);
    if (sentBack.length) {
      const html = sentBack.map(a => {
        const failures = (Array.isArray(a.failures) ? a.failures : []).filter(Boolean).slice(0, 3);
        let body = failures.length
          ? failures.map(f => H.text('Input ' + (f.input == null ? '' : f.input)) + H.diff(f.expected, f.actual)).join('')
          : H.empty('This run kept the counts only, not the failing cases.');
        const ex = a.explanation;
        if (ex && ex.reason) body += H.quote(ex.reason, 'Nemotron · ' + String(ex.verdict || '').replace(/_/g, ' '));
        return H.section('Attempt ' + a.attempt + ' · ' + a.passed + ' / ' + a.total, body);
      }).join('');
      tabs.push({ label: 'Sent back', html });
    }

    return { tabs };
  },
});
