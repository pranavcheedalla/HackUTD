/* 04 — Record. Owner: Pranav. Brief: docs/station-prompts/pranav.md
 * The answer key: what the real COBOL printed for every test input, and where in the source it prints. */
Stations.register(4, {
  agent: 'real COBOL',
  render({ module, H }) {
    const golden = module.golden || [];
    if (!golden.length) return H.empty('No answer key was recorded for this program.');

    const str = v => String(v == null ? '' : v);
    const show = s => (s === '' ? '(empty)' : s.trim() === '' ? '(spaces)' : s);
    const failed = new Set((module.history || []).flatMap(h => (h && h.failures) || [])
      .filter(f => f && f.input != null).map(f => String(f.input)));

    // ---- Answer key
    const shown = golden.slice(0, 40);
    const rows = shown.map((g, i) => [String(i + 1), show(str(g.input)), str(g.output)]);
    const tone = i => (failed.has(str(shown[i].input)) ? 'bad' : '');
    const tinted = shown.some((g, i) => tone(i) === 'bad');
    const answers = H.stats([
      { value: golden.length, label: 'answers recorded' },
      { value: new Set(golden.map(g => str(g.output))).size, label: 'distinct outputs' },
      { value: 'GnuCOBOL', label: 'real compiler', tone: 'dim' },
    ])
      + H.section('Recorded from the real program', H.table(['#', 'Input', 'COBOL output'], rows, { tone })
        + (tinted ? H.text('Tinted rows are the cases a rewrite later got wrong.') : '')
        + (golden.length > 40 ? H.text(`Showing the first 40 of ${golden.length}.`) : ''))
      + H.section('How it was recorded', H.kv([
        ['Program', module.file || module.id || ''],
        ['Compiler', 'GnuCOBOL (cobc)'],
        ['Runs', 'one fresh process per input, 5 second limit'],
        ['Kept', 'exactly what the program printed'],
      ]));

    // ---- Source: highlight the lines that print what was recorded
    const cobol = module.cobol || '';
    let source;
    if (!cobol.trim()) {
      source = H.empty('No COBOL source was saved for this program.');
    } else {
      const word = module.kind === 'subprogram' ? /\bGOBACK\b/i : /\bDISPLAY\b/i;
      const isComment = line => line.charAt(6) === '*' || line.trimStart().startsWith('*>');
      const highlight = cobol.split('\n')
        .map((line, i) => (!isComment(line) && word.test(line) ? i + 1 : 0))
        .filter(Boolean);
      source = H.text('Highlighted lines print the outputs that were recorded.') + H.code(cobol, { highlight });
    }

    return { tabs: [{ label: 'Answer key', html: answers }, { label: 'Source', html: source }] };
  },
});
