/* The replay's narration: one plain sentence and one proof per station, built from the
 * recorded run. galaxy.js draws them on the canvas next to the ring (same type and leader
 * line as the rest of the scene); DETAILS opens the full station readout.
 *
 * Captions.get(n, { module, replay, attempt, attemptIndex, mutation }) →
 *   { sentence, sub?, proof?, note? }
 *   proof: { kind: 'diff', input, expected, actual } | { kind: 'line', text } | { kind: 'pair', left, right }
 * Everything here must come from the replay. If the data isn't there, say less, never invent.
 */
(() => {
  'use strict';
  const NUM = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
  const words = n => (n >= 0 && n <= 10 ? NUM[n] : String(n));
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  const name = id => cap(String(id || '').toLowerCase());
  const lines = src => String(src || '').replace(/\s+$/, '').split('\n').filter(l => l.trim()).length;
  const shown = s => (s === '' ? '(empty)' : /^\s+$/.test(s) ? '(spaces)' : s);
  const clip = (s, n) => ((s = String(s || '')).length > n ? s.slice(0, n - 1) + '…' : s);

  // multi-line outputs: show the first line that differs; an empty rewrite says so
  function firstDiff(expected, actual) {
    const e = String(expected == null ? '' : expected).split('\n'), a = String(actual == null ? '' : actual).split('\n');
    if (!String(actual || '').trim()) return { expected: e[0], actual: '(no output)' };
    for (let i = 0; i < Math.max(e.length, a.length); i++) if ((e[i] || '') !== (a[i] || '')) return { expected: e[i] || '(no line)', actual: a[i] || '(no line)' };
    return { expected: e[0], actual: a[0] };
  }

  // three inputs that show the range: text or codes, a blank, a big number
  function sampleInputs(golden) {
    const ins = (golden || []).map(g => g.input), pick = [];
    const add = f => { const v = ins.find(s => f(s) && !pick.includes(s)); if (v !== undefined) pick.push(v); };
    add(s => /[A-Za-z]/.test(s)); add(s => s.trim() === '' || /\|\s*\|/.test(s)); add(s => /9{4,}/.test(s));
    for (const s of ins) { if (pick.length >= 3) break; if (!pick.includes(s)) pick.push(s); }
    return pick.slice(0, 3).map(s => clip(shown(s), 22));
  }

  const views = {
    1({ module, replay }) {
      const mods = replay.modules || [], n = mods.length;
      const caller = mods.find(m => (m.depends_on || []).length);
      if (caller) {
        const dep = caller.depends_on[0];
        return { sentence: `${cap(words(n))} COBOL programs. ${name(caller.id)} calls ${name(dep)}, so ${name(dep)} goes first.`,
                 proof: { kind: 'line', text: `${String(dep).toUpperCase()}  ──→  ${String(caller.id).toUpperCase()}` } };
      }
      return { sentence: n === 1 ? 'One COBOL program to move to Python.' : `${cap(words(n))} COBOL programs to move to Python.`,
               proof: { kind: 'line', text: (module.file || module.id).toUpperCase() } };
    },
    2({ module }) {
      const rule = ((module.spec || {}).business_rules || [])[0];
      return { sentence: 'Nemotron read the COBOL and wrote down what it does, in plain English.',
               proof: rule ? { kind: 'line', text: `“${clip(rule, 96)}”` } : null };
    },
    3({ module }) {
      const n = (module.golden || []).length || module.tests_total;
      const sample = sampleInputs(module.golden);
      return { sentence: `Nemotron invented ${n} tricky inputs to try to break it.`, sub: 'Limits, blanks, bad codes.',
               proof: sample.length ? { kind: 'line', text: sample.join('   ·   ') } : null };
    },
    4({ module }) {
      const golden = module.golden || [];
      const failed = new Set((module.history || []).flatMap(a => (a.failures || []).map(f => f.input)));
      const g = golden.find(c => failed.has(c.input)) || golden.find(c => c.input.trim()) || golden[0];
      return { sentence: 'We ran the real COBOL on every input and saved exactly what it printed.',
               proof: g ? { kind: 'pair', left: clip(shown(g.input), 22), right: clip(String(g.output).split('\n')[0] + (String(g.output).includes('\n') ? '  …' : ''), 34) } : null };
    },
    5({ module, attemptIndex }) {
      const deps = (module.depends_on || []).map(name);
      const retry = attemptIndex > 0;
      return { sentence: retry ? 'Nemotron fixed the Python, using the cases it got wrong.' : 'Nemotron rewrote it in Python.',
               sub: deps.length ? `It reuses the verified ${deps.join(', ')} instead of copying it.` : null,
               proof: { kind: 'line', text: `${lines(module.cobol)} LINES COBOL   →   ${lines(module.python)} LINES PYTHON` } };
    },
    6({ module, attempt, mutation }) {
      const a = attempt || {}, total = a.total || module.tests_total, passed = a.passed != null ? a.passed : module.tests_passed;
      if (passed < total) {
        const f = (a.failures || [])[0], ex = a.explanation || {};
        return { sentence: mutation ? 'We planted a one-cent bug. The original COBOL caught it.' : 'The original COBOL judged the rewrite.',
                 sub: `${passed} of ${total} outputs matched, so it went back for a fix.`,
                 proof: f ? { kind: 'diff', input: clip(shown(f.input), 30), ...firstDiff(f.expected, f.actual) } : { kind: 'line', text: `${passed} / ${total} MATCH` },
                 note: ex.reason || null };
      }
      return { sentence: 'Every output matches the original COBOL.', sub: 'Checked character by character.',
               proof: { kind: 'line', text: `${passed} / ${total} MATCH` } };
    },
    7({ module }) {
      const h = module.heldout;
      return { sentence: h && h.total ? `Verified, including ${h.total} inputs it never saw.` : 'Verified. Every recorded output matches the original.',
               proof: { kind: 'line', text: `${module.tests_passed} / ${module.tests_total}` + (h && h.total ? `   ·   ${h.passed} / ${h.total} UNSEEN` : '') } };
    },
  };

  window.Captions = {
    get(n, ctx) {
      const v = views[n]; if (!v || !ctx || !ctx.module) return null;
      try { return v(ctx); } catch (err) { console.error(`caption ${n}:`, err); return null; }
    },
    // which stops narrate: everything for the first program, then only what differs
    narrates(mi, at) { return mi === 0 || at >= 4; },
  };
})();
