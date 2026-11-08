/* 01 — Discover. Owner: Hemant. Brief: docs/station-prompts/hemant.md
 * The whole codebase the run migrated: programs, who calls whom, order, shared copybooks. */
Stations.register(1, {
  agent: 'codebase scan',
  render({ module, replay, H }) {
    const MAX = 40;
    const capped = (items, html) => html + (items.length > MAX ? H.text(`Showing the first ${MAX} of ${items.length}.`) : '');
    const mods = (replay && replay.modules) || [];
    const cur = (module || {}).id;
    const deps = m => m.depends_on || [];
    const up = s => String(s || '').toUpperCase();
    const done = m => m.status === 'done';
    const plural = (n, word) => (n === 1 ? word : word + 's');
    const subs = mods.filter(m => m.kind === 'subprogram').length;
    const calls = mods.reduce((n, m) => n + deps(m).length, 0);

    const stats = H.stats([
      { value: mods.length, label: plural(mods.length, 'program') },
      { value: subs, label: plural(subs, 'subprogram') },
      { value: calls, label: plural(calls, 'call') },
    ]);

    const callers = mods.filter(m => deps(m).length);
    const chain = callers.length
      ? callers.map(m => H.chain([...deps(m).map(up), up(m.id)])).join('')
      : H.empty('No program calls another.');

    const shown = mods.slice(0, MAX);
    const rows = shown.map(m => [
      m.id === cur ? H.raw(H.esc(m.file) + ' ' + H.tag('on screen', 'accent')) : m.file,
      m.kind,
      deps(m).join(', ') || '—',
      done(m) ? 'verified' : (m.error || 'not verified'),
    ]);
    const programs = mods.length
      ? capped(mods, H.table(['File', 'Kind', 'Calls', 'Result'], rows, { tone: i => done(shown[i]) ? 'ok' : 'bad' }))
      : H.empty('No programs were recorded in this run.');

    const order = mods.length
      ? capped(mods, H.list(shown.map(m => up(m.id)), true))
        + H.text('Programs are migrated callees first, so a caller can reuse code that is already verified.')
      : H.empty('No migration order was recorded.');

    // copybook name -> files that COPY it (fixed-format comment lines, column 7 = '*', are skipped)
    const books = {};
    for (const m of mods) {
      for (const line of String(m.cobol || '').split('\n')) {
        if (line[6] === '*') continue;
        const hit = /^\s*COPY\s+["']?([A-Z0-9-]+)/i.exec(line);
        if (!hit) continue;
        const name = hit[1].toUpperCase(), files = books[name] || (books[name] = []);
        if (!files.includes(m.file)) files.push(m.file);
      }
    }
    const names = Object.keys(books);
    const copybooks = names.length
      ? capped(names, H.kv(names.slice(0, MAX).map(n => [n, books[n].join(', ')])))
      : H.empty('No shared copybooks.');

    return stats
      + H.section('Call chain', chain)
      + H.section('Programs', programs)
      + H.section('Migration order', order)
      + H.section('Shared copybooks', copybooks);
  },
});
