/* The end of a live run: the COBOL that went in, and the Python Nemotron wrote in this run.
 * Everything here comes from the run that just finished (GET /api/runs/<session>/replay): the source,
 * the verified Python, the test counts, and the run's own Nemotron call log (runs/llm_calls.jsonl),
 * each call matched to the step it finished. Nothing is written ahead of time. Esc closes it. */
(() => {
  const style = document.createElement('style');
  style.textContent = `
  .reveal-shade { position: fixed; inset: 0 0 auto 0; height: 88vh; z-index: 5; pointer-events: none; opacity: 0; transition: opacity .8s ease;
    background: linear-gradient(180deg, rgba(4,3,10,.97) 0%, rgba(4,3,10,.94) 70%, rgba(4,3,10,.6) 88%, rgba(4,3,10,0) 100%); }
  .reveal-shade.on { opacity: 1; }
  .reveal { position: fixed; left: 0; right: 0; top: 0; z-index: 6; box-sizing: border-box; padding: 28px 48px 0; font-family: var(--mono);
    display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr); column-gap: 48px; row-gap: 14px; animation: reveal-drop .8s cubic-bezier(.2,.75,.2,1); }
  .reveal[hidden], body.intake-on .reveal { display: none !important; }
  @keyframes reveal-drop { from { opacity: 0; transform: translateY(-28px); } to { opacity: 1; transform: none; } }
  .rv-head { grid-column: 1 / -1; display: flex; align-items: baseline; gap: 22px; flex-wrap: wrap; }
  .rv-title { font-size: 10px; letter-spacing: 5px; text-transform: uppercase; color: rgba(242,241,248,.92); }
  .rv-live { display: inline-flex; align-items: center; gap: 8px; font-size: 9px; letter-spacing: 3px; text-transform: uppercase; color: #b9f0dc; }
  .rv-live::before { content: ''; width: 4px; height: 4px; border-radius: 50%; background: currentColor; box-shadow: 0 0 7px currentColor; }
  .rv-sess { font-size: 9px; letter-spacing: 2.5px; text-transform: uppercase; color: rgba(232,234,242,.32); }
  .rv-close { margin-left: auto; background: none; border: 0; cursor: pointer; font: 9px var(--mono); letter-spacing: 3px; text-transform: uppercase; color: rgba(232,234,242,.45); padding: 2px 0; }
  .rv-close:hover { color: rgba(242,241,248,.9); }
  .rv-proof { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 8px 26px; align-items: baseline; padding-bottom: 6px; }
  .rv-calls { display: flex; flex-wrap: wrap; gap: 6px 22px; }
  .rv-call { font-size: 11px; color: rgba(232,234,242,.7); white-space: nowrap; }
  .rv-call b { font-weight: 400; font-size: 9px; letter-spacing: 3px; text-transform: uppercase; color: rgba(212,196,255,.85); margin-right: 8px; }
  .rv-model { font-size: 9px; letter-spacing: 2px; color: rgba(232,234,242,.35); }
  .rv-match { font-size: 9.5px; letter-spacing: 3px; text-transform: uppercase; color: #b9f0dc; text-shadow: 0 0 10px rgba(150,240,210,.35); }
  .rv-col { min-width: 0; display: flex; flex-direction: column; gap: 10px; }
  .rv-h { display: flex; justify-content: space-between; gap: 12px; font-size: 9px; letter-spacing: 3px; text-transform: uppercase; color: rgba(232,234,242,.42); }
  .rv-h span:first-child { color: rgba(242,241,248,.85); }
  .rv-col.py .rv-h span:first-child { color: #d4c4ff; }
  .rv-code { margin: 0; max-height: 56vh; overflow: auto; font-size: 11.5px; line-height: 1.62; white-space: pre; color: rgba(232,234,242,.55);
    border-left: 1px solid rgba(232,234,242,.12); padding-left: 14px; }
  .rv-col.py .rv-code { color: rgba(240,238,250,.9); border-left-color: rgba(212,196,255,.45); }
  .rv-ln { display: inline-block; width: 28px; margin-right: 14px; text-align: right; color: rgba(232,234,242,.16); user-select: none; }
  .rv-col.py .rv-ln { color: rgba(212,196,255,.3); }
  .rv-line { display: block; }
  .rv-col.py .rv-line { opacity: 0; transform: translateX(-6px); animation: rv-line .35s ease forwards; }
  @keyframes rv-line { to { opacity: 1; transform: none; } }
  @media (max-width: 900px) { .reveal { grid-template-columns: 1fr; padding: 18px 18px 0; } .rv-code { max-height: 30vh; } }
  @media (prefers-reduced-motion: reduce) { .reveal, .rv-col.py .rv-line { animation: none; opacity: 1; transform: none; } }`;
  document.head.appendChild(style);

  const shade = document.createElement('div'); shade.className = 'reveal-shade'; shade.setAttribute('aria-hidden', 'true');
  const box = document.createElement('section'); box.className = 'reveal'; box.hidden = true; box.setAttribute('aria-label', 'COBOL in, Python out');
  box.innerHTML = `
    <div class="rv-head"><span class="rv-title" id="rv-title"></span><span class="rv-live">Live · real Nemotron run</span>
      <span class="rv-sess" id="rv-sess"></span><button class="rv-close" id="rv-close">Close  ·  Esc</button></div>
    <div class="rv-proof"><div class="rv-calls" id="rv-calls"></div><span class="rv-model" id="rv-model"></span><span class="rv-match" id="rv-match"></span></div>
    <div class="rv-col cbl"><div class="rv-h"><span id="rv-cbl-h"></span><span>the COBOL that went in</span></div><pre class="rv-code" id="rv-cbl"></pre></div>
    <div class="rv-col py"><div class="rv-h"><span id="rv-py-h"></span><span id="rv-py-when"></span></div><pre class="rv-code" id="rv-py"></pre></div>`;
  document.body.append(shade, box);
  const $ = id => document.getElementById(id);
  let shownFor = null, closedFor = null;

  $('rv-close').onclick = () => { closedFor = shownFor; hide(); };
  addEventListener('keydown', e => { if (e.key === 'Escape' && !box.hidden) { closedFor = shownFor; hide(); } });

  function hide() { box.hidden = true; shade.classList.remove('on'); }
  const secs = s => `${(+s).toFixed(1)} s`;
  const clock = d => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  function lines(el, text, stagger) {
    el.replaceChildren(...String(text || '').replace(/\n$/, '').split('\n').map((l, i) => {
      const row = document.createElement('span'), n = document.createElement('span');
      row.className = 'rv-line'; n.className = 'rv-ln'; n.textContent = i + 1;
      row.append(n, document.createTextNode(l || ' '));
      if (stagger) row.style.animationDelay = `${Math.min(i * .018, 2.6)}s`;  // the new file fills in, top to bottom
      return row;
    }));
    el.scrollTop = 0;
  }

  // each call is credited to the step whose result landed when it finished (events are local time, calls UTC)
  function steps(rep) {
    const names = { extract_spec: 'spec', record: 'test inputs', rewrite: 'python', explain: 'explanation' };
    const evs = (rep.events || []).map(e => [Date.parse(e.t), e.node]).filter(([t]) => isFinite(t));
    return (rep.llm_calls || []).filter(c => c.source === 'live' && c.ok).map(c => {
      const end = Date.parse(c.ts), next = evs.find(([t]) => t >= end - 1500);
      return { what: (next && names[next[1]]) || 'call', seconds: c.seconds, model: c.model_id, end };
    });
  }

  function show(rep) {
    const m = rep.modules[0];
    $('rv-title').textContent = `${m.id.toUpperCase()}  ·  COBOL in, Python out`;
    $('rv-sess').textContent = `session ${rep.session || rep.name}`;
    const calls = steps(rep);
    $('rv-calls').replaceChildren(...calls.map(c => {
      const el = document.createElement('span'), b = document.createElement('b');
      el.className = 'rv-call'; b.textContent = c.what; el.append(b, secs(c.seconds)); return el;
    }));
    const models = [...new Set(calls.map(c => c.model).filter(Boolean))];
    $('rv-model').textContent = calls.length ? `${calls.length} live Nemotron call${calls.length > 1 ? 's' : ''}  ·  ${models.join(', ')}` : '';
    $('rv-match').textContent = `Verified  ·  ${m.tests_passed} / ${m.tests_total} outputs match the real COBOL`;
    $('rv-cbl-h').textContent = m.file || `${m.id}.cbl`;
    $('rv-py-h').textContent = `${m.id}.py`;
    const py = calls.filter(c => c.what === 'python').pop();
    $('rv-py-when').textContent = py ? `written by Nemotron at ${clock(new Date(py.end))}` : 'written by Nemotron in this run';
    lines($('rv-cbl'), m.cobol, false);
    lines($('rv-py'), m.python, true);
    box.hidden = false; shade.classList.add('on');
    // once the new file has filled in, bring the logic into view on both sides: PROCEDURE DIVISION, def main
    const key = rep.session || rep.name;
    setTimeout(() => {
      if (shownFor !== key || box.hidden) return;
      focusOn($('rv-cbl'), /PROCEDURE\s+DIVISION/i); focusOn($('rv-py'), /^\s*def\s+main\s*\(/);
    }, 2400);
  }
  function focusOn(el, re) {
    const row = [...el.children].find(r => re.test(r.lastChild ? r.lastChild.textContent : ''));
    if (row) el.scrollTo({ top: Math.max(0, row.offsetTop - el.offsetTop - 18), behavior: 'smooth' });
  }

  // show once a live, one-program run is verified and the galaxy has landed on its summary
  setInterval(() => {
    const v = window.galaxy && galaxy.liveView && galaxy.liveView();
    const rep = v && v.R, m = rep && rep.modules && rep.modules[0];
    const ready = rep && rep.finished && rep.modules.length === 1 && m && m.status === 'done' && m.python && v.beat && v.beat.k === 'outro';
    if (!ready) { if (!box.hidden && !(rep && rep.finished)) hide(); if (!rep || !rep.live) { shownFor = null; hide(); } return; }
    const key = rep.session || rep.name;
    if (key === shownFor || key === closedFor) return;
    shownFor = key; show(rep);
  }, 250);
})();
