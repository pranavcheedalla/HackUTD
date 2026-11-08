/* 02 — Read. Owner: Hemant. Brief: docs/station-prompts/hemant.md
 * The spec Nemotron wrote for the program on screen, and the COBOL lines it describes. */
Stations.register(2, {
  agent: 'Nemotron',
  render({ module, H }) {
    const MAX = 40;
    const capped = (items, html) => html + (items.length > MAX ? H.text(`Showing the first ${MAX} of ${items.length}.`) : '');
    const arr = x => (Array.isArray(x) ? x : []);
    const mod = module || {};
    const spec = mod.spec || {};
    const rules = arr(spec.business_rules), edges = arr(spec.edge_cases), quirks = arr(spec.quirks);
    const inputs = arr(spec.inputs), outputs = arr(spec.outputs);
    const fields = list => capped(list, H.table(['Name', 'Type', 'Format'],
      list.slice(0, MAX).map(f => [(f || {}).name, (f || {}).type, (f || {}).format])));

    let specHtml;
    if (!spec.summary && !rules.length && !edges.length && !quirks.length && !inputs.length && !outputs.length) {
      specHtml = H.empty('No spec was recorded for this program.');
    } else {
      specHtml = H.stats([
        { value: rules.length, label: 'business rules' },
        { value: edges.length, label: 'edge cases' },
        { value: quirks.length, label: 'COBOL quirks' },
      ])
        + H.section('Summary', spec.summary ? H.text(spec.summary) : H.empty('No summary was recorded.'))
        + H.section('Business rules', rules.length ? capped(rules, H.list(rules.slice(0, MAX), true)) : H.empty('No business rules were recorded.'))
        + (inputs.length ? H.section('Inputs', fields(inputs)) : '')
        + (outputs.length ? H.section('Outputs', fields(outputs)) : '')
        + H.section('Edge cases', edges.length ? capped(edges, H.list(edges.slice(0, MAX))) : H.empty('No edge cases were recorded.'))
        + H.section('COBOL quirks', quirks.length ? capped(quirks, H.list(quirks.slice(0, MAX))) : H.empty('None noted.'));
    }

    // logic lines: statements that match the spec's rules, skipping comments (column 7 '*', or '*>')
    const logic = /\b(IF|ELSE|EVALUATE|WHEN|COMPUTE|MOVE|ADD|SUBTRACT|MULTIPLY|DIVIDE|PERFORM|CALL)\b/i;
    const highlight = [];
    String(mod.cobol || '').split('\n').forEach((line, i) => {
      if (line[6] === '*' || line.trim().startsWith('*>')) return;
      if (logic.test(line)) highlight.push(i + 1);
    });
    const sourceHtml = mod.cobol
      ? H.text('Highlighted lines are the logic the spec describes.') + H.code(mod.cobol, { highlight })
      : H.empty('No COBOL source was recorded for this program.');

    return { tabs: [{ label: 'Spec', html: specHtml }, { label: 'Source', html: sourceHtml }] };
  },
});
