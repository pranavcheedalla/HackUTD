/* 03 — Probe. Owner: Pranav. Brief: docs/station-prompts/pranav.md
 * The test inputs (module.golden[].input), grouped by the kind of case each one probes. */
Stations.register(3, {
  agent: 'Nemotron',
  render({ module, H }) {
    const golden = module.golden || [];
    if (!golden.length) return H.empty('No answer key was recorded for this program.');

    const inputs = golden.map(g => String(g.input == null ? '' : g.input));
    const show = s => (s === '' ? '(empty)' : s.trim() === '' ? '(spaces)' : s);
    const fields = s => s.split('|');
    const isNumber = f => /^\s*[-+]?(\d+\.?\d*|\.\d+)\s*$/.test(f);

    // each input goes into the FIRST group it matches, in this order
    const groups = [
      ['Blank and empty', s => s.trim() === '' || (s.includes('|') && fields(s).some(f => f.trim() === ''))],
      ['Text and codes', s => /[A-Za-z]/.test(s)],
      ['Maximums', s => /9{4,}/.test(s)],
      ['Zeros', s => { const nums = fields(s).filter(isNumber); return nums.length > 0 && nums.every(f => Number(f) === 0); }],
      ['Boundaries and typical', () => true],
    ].map(([name, test]) => ({ name, test, items: [] }));
    for (const s of inputs) groups.find(g => g.test(s)).items.push(s);
    const used = groups.filter(g => g.items.length);

    let html = H.stats([
      { value: inputs.length, label: 'test inputs' },
      { value: used.length, label: 'kinds of case' },
    ]);
    for (const g of used) {
      const shown = g.items.slice(0, 12).map(show);
      html += H.section(g.name, H.list(shown) + (g.items.length > 12 ? H.text(`…and ${g.items.length - 12} more.`) : ''));
    }
    html += H.section('Why', H.text('Each input is chosen to hit a branch, a limit, or bad data, so the rewrite has to match the COBOL everywhere, not only on easy cases.'));

    const caught = [...new Set((module.history || []).flatMap(h => (h && h.failures) || [])
      .filter(f => f && f.input != null).map(f => String(f.input)))];
    if (caught.length) {
      html += H.section('Caught the rewrite', H.list(caught.slice(0, 40).map(show))
        + (caught.length > 40 ? H.text(`Showing the first 40 of ${caught.length}.`) : ''));
    }
    return html;
  },
});
