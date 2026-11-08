/* Station views: shared registry and the ONLY building blocks a station may use.
 *
 * Each station file (web/stations/0N-name.js) calls:
 *
 *   Stations.register(N, {
 *     agent: 'Nemotron Super',             // optional: shown in the panel header
 *     render({ module, replay, H }) {      // returns an HTML string, or { tabs: [{ label, html }] }
 *       return H.section('Label', H.code(module.cobol));
 *     },
 *     overlay(api) { ... },                // optional: draws on the canvas at this station's ring
 *   });
 *
 * Rules that keep every station looking the same:
 *  - Build the panel only from the H.* helpers below. No inline styles, no new CSS, no colours.
 *  - Text you pass in is escaped by the helpers. Pass HTML only where a helper says "html".
 *  - Use real replay data only. When data is missing, show H.empty('…'), never made-up values.
 *  - Sentence case in the panel ("Business rules"); the canvas uses SPACED CAPS (api.txt).
 */
(() => {
  'use strict';
  const views = {};
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));

  // where expected and actual first/last differ, so only the changed characters are lit
  function diffSpans(a, b) {
    a = String(a == null ? '' : a); b = String(b == null ? '' : b);
    let i = 0; while (i < a.length && i < b.length && a[i] === b[i]) i++;
    let j = 0; while (j < a.length - i && j < b.length - i && a[a.length - 1 - j] === b[b.length - 1 - j]) j++;
    const cut = s => [s.slice(0, i), s.slice(i, s.length - j), s.slice(s.length - j)];
    return [cut(a), cut(b)];
  }

  const H = {
    esc,

    /** A titled block. label: text. html: inner html (from other helpers). */
    section: (label, html) => `<section class="st-sec"><div class="st-label">${esc(label)}</div>${html || ''}</section>`,

    /** One sentence or short paragraph of body text. */
    text: s => `<p class="st-text">${esc(s)}</p>`,

    /** Muted message for missing data. */
    empty: s => `<p class="st-empty">${esc(s)}</p>`,

    /** Big thin numbers in a row: items = [{ value, label, tone }] (tone: 'ok' | 'bad' | 'dim'). */
    stats: items => `<div class="st-stats">${items.map(it =>
      `<div class="st-stat ${it.tone ? 'st-' + esc(it.tone) : ''}"><div class="st-stat-v">${esc(it.value)}</div><div class="st-stat-l">${esc(it.label)}</div></div>`).join('')}</div>`,

    /** Small tag. tone: 'ok' | 'bad' | 'dim' | 'accent'. */
    tag: (s, tone = 'dim') => `<span class="st-tag st-${esc(tone)}">${esc(s)}</span>`,

    /** key → value rows: pairs = [[key, value], ...]. value may be html if wrapped with H.raw(). */
    kv: pairs => `<dl class="st-kv">${pairs.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v && v.__html ? v.__html : esc(v)}</dd>`).join('')}</dl>`,

    /** Mark a string as already-built html (only for H.kv values and H.table cells). */
    raw: html => ({ __html: html }),

    /** Bulleted (or numbered) list of plain strings. */
    list: (items, numbered = false) => `<${numbered ? 'ol' : 'ul'} class="st-list">${items.map(s => `<li>${s && s.__html ? s.__html : esc(s)}</li>`).join('')}</${numbered ? 'ol' : 'ul'}>`,

    /** Table. headers = ['Input', 'Output']; rows = [[cell, cell], ...]; cells: text or H.raw(html).
     *  opts.tone(rowIndex) → 'ok' | 'bad' | '' to tint a row. */
    table: (headers, rows, opts = {}) => `<table class="st-table"><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${
      rows.map((r, i) => `<tr class="${opts.tone ? 'st-' + (opts.tone(i) || 'none') : ''}">${r.map(c => `<td>${c && c.__html ? c.__html : esc(c === '' ? '(empty)' : c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`,

    /** Source code with line numbers. opts.highlight: array of 1-based lines to light up;
     *  opts.from / opts.to: show only that line range (1-based, inclusive). */
    code: (src, opts = {}) => {
      const lines = String(src || '').replace(/\s+$/, '').split('\n'), hi = new Set(opts.highlight || []);
      const from = Math.max(1, opts.from || 1), to = Math.min(lines.length, opts.to || lines.length);
      let out = '';
      for (let n = from; n <= to; n++) out += `<div class="st-line${hi.has(n) ? ' st-hi' : ''}"><span class="st-ln">${n}</span>${esc(lines[n - 1]) || ' '}</div>`;
      return `<div class="st-code">${out || '<div class="st-line">(empty)</div>'}</div>`;
    },

    /** Two columns side by side. left/right: html. labels: ['COBOL', 'Python']. */
    columns: (left, right, labels = ['', '']) =>
      `<div class="st-cols"><div><div class="st-label">${esc(labels[0])}</div>${left}</div><div><div class="st-label">${esc(labels[1])}</div>${right}</div></div>`,

    /** Expected vs actual, only the differing characters lit (the same look as the canvas). */
    diff: (expected, actual, labels = ['COBOL', 'Rewrite']) => {
      const [a, b] = diffSpans(expected, actual), row = (lab, p, cls) =>
        `<div class="st-diff-row"><span class="st-diff-l">${esc(lab)}</span><span class="st-diff-v">${esc(p[0])}<b class="${cls}">${esc(p[1]) || ' '}</b>${esc(p[2])}</span></div>`;
      return `<div class="st-diff">${row(labels[0], a, 'st-same')}${row(labels[1], b, 'st-wrong')}</div>`;
    },

    /** Nemotron's words: quote = the reason, by = e.g. 'Nemotron · new code bug'. */
    quote: (quote, by) => `<blockquote class="st-quote">${esc(quote)}${by ? `<cite>${esc(by)}</cite>` : ''}</blockquote>`,

    /** A left-to-right chain of names: ['DISCOUNT', 'INVOICE'] → DISCOUNT ──→ INVOICE. */
    chain: names => `<div class="st-chain">${names.map(esc).join('<span class="st-arrow">──→</span>')}</div>`,

    /** Small dots, one per test: states = ['ok' | 'bad' | 'dim', ...]. Clicking is not wired. */
    dots: states => `<div class="st-dots">${states.map(s => `<i class="st-dot st-${esc(s)}"></i>`).join('')}</div>`,
  };

  window.Stations = {
    H,
    register(n, view) {
      if (!(n >= 1 && n <= 7) || !view || typeof view.render !== 'function') throw new Error(`Stations.register(${n}): needs 1-7 and a render()`);
      views[n] = view;
    },
    get: n => views[n] || null,
  };
})();
