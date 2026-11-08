/* Human hints (live runs only). Owner: Hemant.
 * While a live run is in progress (#live=<session>, served by tools/serve.py), a reviewer can send
 * a program a hint. The pipeline adds it to the spec its next rewrite attempt sees
 * (pipeline/graph.py read_hints). A hint only guides the rewrite: acceptance still needs every
 * golden case to match the real COBOL. Recordings show nothing here. */
(() => {
  const POLL_MS = 1500, MAX = 500;
  const style = document.createElement('style');
  style.textContent = `
  .hint { position: fixed; right: 24px; bottom: 52px; z-index: 4; width: min(360px, calc(100vw - 48px)); box-sizing: border-box;
    display: flex; flex-direction: column; gap: 12px; padding: 18px 20px 16px; font-family: var(--mono);
    background: rgba(6,5,13,.9); box-shadow: 0 0 22px 8px rgba(6,5,13,.75);
    border-top: 1px solid rgba(232,234,242,.12); opacity: .55; transition: opacity .3s, border-color .4s; }
  .hint:hover, .hint:focus-within, .hint.ask { opacity: 1; }
  .hint.ask { border-top-color: rgba(212,196,255,.7); }
  .hint[hidden], .hint [hidden], body.intake-on .hint, .hint.under-panel { display: none; }
  .hint-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
  .hint-title { font-size: 9.5px; letter-spacing: 3.5px; text-transform: uppercase; color: rgba(242,241,248,.85); }
  .hint-state { font-size: 9px; letter-spacing: 2.5px; text-transform: uppercase; color: rgba(232,234,242,.4); text-align: right; }
  .hint.ask .hint-state { color: #d4c4ff; text-shadow: 0 0 10px rgba(200,180,255,.45); }
  .hint-why { font: 400 13px/1.5 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; color: rgba(232,234,242,.68); }
  .hint-why:empty { display: none; }
  .hint select { appearance: none; -webkit-appearance: none; align-self: flex-start; background: none; border: 0; border-bottom: 1px solid rgba(232,234,242,.12);
    color: var(--ink); font: 10px var(--mono); letter-spacing: 3px; text-transform: uppercase; padding: 3px 4px 3px 0; cursor: pointer; }
  .hint select option { background: #111018; }
  .hint textarea { resize: none; box-sizing: border-box; width: 100%; min-height: 54px; background: rgba(232,234,242,.03); border: 0;
    border-bottom: 1px solid rgba(232,234,242,.14); color: rgba(242,241,248,.92); padding: 8px 2px;
    font: 400 13px/1.5 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; outline: none; }
  .hint textarea:focus { border-bottom-color: rgba(212,196,255,.7); }
  .hint textarea::placeholder { color: rgba(232,234,242,.3); }
  .hint-act { display: flex; align-items: baseline; gap: 16px; }
  .hint-act button { background: none; border: 0; padding: 4px 0; cursor: pointer; font: 9.5px var(--mono); letter-spacing: 3px; text-transform: uppercase;
    color: #d4c4ff; display: inline-flex; align-items: center; gap: 8px; flex: none; }
  .hint-act button::before { content: ''; width: 4px; height: 4px; border-radius: 50%; background: currentColor; box-shadow: 0 0 6px currentColor; }
  .hint-act button:hover { color: #efe9ff; }
  .hint-act button[disabled] { opacity: .35; cursor: default; }
  .hint-msg { font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: rgba(232,234,242,.45); }
  .hint-msg.bad { color: #ffb8cb; }
  .hint-log { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; max-height: 120px; overflow: auto; }
  .hint-log li { font: 400 12px/1.45 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; color: rgba(232,234,242,.62); }
  .hint-log b { font: 9px var(--mono); letter-spacing: 2.5px; text-transform: uppercase; font-weight: 400; margin-right: 8px; color: rgba(232,234,242,.4); }
  .hint-log .used b { color: #b9f0dc; }
  .hint-log .waiting b { color: #d4c4ff; }`;
  document.head.appendChild(style);

  const box = document.createElement('section');
  box.className = 'hint'; box.hidden = true; box.setAttribute('aria-label', 'Send a hint to the agents');
  box.innerHTML = `
    <div class="hint-head"><span class="hint-title">Human hint</span><span class="hint-state" id="hint-state"></span></div>
    <div class="hint-why" id="hint-why"></div>
    <select id="hint-mod" aria-label="Program"></select>
    <textarea id="hint-note" maxlength="${MAX}" aria-label="Hint"
      placeholder="What did the agent miss? e.g. amounts truncate to the cent, never round"></textarea>
    <div class="hint-act"><button id="hint-send">Send hint</button><span class="hint-msg" id="hint-msg" role="status"></span></div>
    <ol class="hint-log" id="hint-log"></ol>`;
  document.body.appendChild(box);
  const $ = id => document.getElementById(id);
  const stateEl = $('hint-state'), whyEl = $('hint-why'), modSel = $('hint-mod'), note = $('hint-note'),
        sendBtn = $('hint-send'), msg = $('hint-msg'), log = $('hint-log'), panel = $('panel');

  let session = null, rep = null, picked = null, lastAsk = null, sending = false;
  const sent = {};  // module -> notes sent from this page, until the pipeline records them
  const norm = s => String(s || '').split(/\s+/).filter(Boolean).join(' ');
  const upper = s => String(s || '').toUpperCase();

  // galaxy.js handles keys on window (space pauses, R restarts, 1-7 open stations): typing must not reach it
  note.addEventListener('keydown', e => {
    e.stopPropagation();
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    if (e.key === 'Escape') note.blur();
  });
  modSel.addEventListener('keydown', e => e.stopPropagation());
  modSel.onchange = () => { picked = modSel.value; render(); };
  sendBtn.onclick = send;

  // which program needs a person right now: one holding its retry for a hint, else one that just failed a verify
  function ask(m) {
    const evs = (rep.events || []).filter(e => e.module === m.id), last = evs[evs.length - 1];
    if (!last) return null;
    const hist = m.history || [], h = hist[hist.length - 1];
    if (last.node === 'hint_window') {
      const secs = +((/up to ([\d.]+)s/.exec(last.msg || '') || [])[1] || 0);
      const left = Math.max(0, Math.round(secs - (Date.now() - new Date(last.t)) / 1000));
      return { m, waiting: true, left, h };
    }
    if (last.node === 'verify' && h && h.passed < h.total) return { m, waiting: false, h };
    return null;
  }

  function render() {
    const open = rep.modules.filter(m => m.status !== 'done' && m.status !== 'failed');
    const used = rep.modules.flatMap(m => (m.human_hints || []).map(h => ({ ...h, id: m.id })));
    const live = !rep.finished && open.length > 0;
    box.hidden = !live && !used.length;
    if (box.hidden) return;

    const need = live ? open.map(ask).find(Boolean) : null;
    if (need && need.m.id !== lastAsk) picked = need.m.id;  // a new request for help moves the picker to it
    lastAsk = need ? need.m.id : null;
    const current = open.find(m => (rep.events || []).some(e => e.module === m.id)) || open[0];
    if (!open.some(m => m.id === picked)) picked = (need && need.m.id) || (current && current.id) || null;

    box.classList.toggle('ask', !!need);
    stateEl.textContent = !live ? 'run finished'
      : need ? (need.waiting ? `waiting · ${need.left}s` : 'retrying soon') : 'optional';
    whyEl.textContent = !live ? 'Hints this run used are listed below.'
      : need ? `${upper(need.m.id)} matched ${need.h ? `${need.h.passed} of ${need.h.total}` : 'only some'} cases on attempt ${need.h ? need.h.attempt : need.m.attempts}. `
             + (need.h && need.h.explanation && need.h.explanation.reason ? `Why: ${need.h.explanation.reason} ` : '')
             + 'A hint goes into its next attempt.'
      : 'Send any program a hint; its next rewrite attempt follows it.';

    const opts = open.map(m => [m.id, upper(m.id) + (m.status === 'pending' ? ' · not started' : '')]);
    if (modSel.dataset.opts !== JSON.stringify(opts)) {
      modSel.replaceChildren(...opts.map(([v, label]) => new Option(label, v)));
      modSel.dataset.opts = JSON.stringify(opts);
    }
    if (picked) modSel.value = picked;
    for (const el of [modSel, note]) el.hidden = !live;
    sendBtn.parentElement.hidden = !live;

    const usedNotes = new Set(used.map(h => `${h.id}|${norm(h.note)}`));
    const waiting = Object.entries(sent).flatMap(([id, notes]) => notes.filter(n => !usedNotes.has(`${id}|${n}`)).map(n => ({ id, note: n })));
    log.replaceChildren(...used.map(h => item('used', `${h.id} · attempt ${h.attempt}`, h.note)),
                        ...(live ? waiting.map(h => item('waiting', `${h.id} · queued`, h.note)) : []));
  }

  function item(kind, label, text) {
    const li = document.createElement('li'), b = document.createElement('b');
    li.className = kind; b.textContent = label; li.append(b, text);
    return li;
  }

  async function send() {
    const module = modSel.value, text = norm(note.value).slice(0, MAX);
    if (sending || !session || !module) return;
    if (!text) { say('Write a hint first.', true); return; }
    sending = true; sendBtn.disabled = true;
    try {
      const r = await fetch(`api/runs/${session}/feedback`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ module, note: text }) });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
      (sent[module] = sent[module] || []).push(text);
      note.value = '';
      say(`Sent to ${upper(module)}`);
      if (rep) render();
    } catch (err) {
      say(err.message, true);
    } finally {
      sending = false; sendBtn.disabled = false;
    }
  }

  function say(text, bad = false) { msg.textContent = text; msg.classList.toggle('bad', bad); }

  async function poll() {
    const m = /^#live=([0-9a-z-]+)$/.exec(location.hash);
    if (!m) { box.hidden = true; session = rep = null; return setTimeout(poll, POLL_MS); }
    if (m[1] !== session) { session = m[1]; rep = null; picked = lastAsk = null; for (const k in sent) delete sent[k]; say(''); }
    try {
      const r = await fetch(`api/runs/${session}/replay`, { cache: 'no-store' });
      if (r.status === 200) { rep = await r.json(); render(); }
    } catch (err) { /* the galaxy already reports a lost run */ }
    box.classList.toggle('under-panel', !!(panel && panel.classList.contains('open')));
    // sit above the toolbar and the canvas's LIVE label, however many lines the toolbar wraps to
    const bar = document.querySelector('.controls');
    if (bar) box.style.bottom = `${Math.max(52, innerHeight - bar.getBoundingClientRect().top + 44)}px`;
    setTimeout(poll, POLL_MS);
  }
  poll();
})();
