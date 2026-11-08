/* Human feedback (live runs only). Owner: Hemant.
 * When the agent cannot modernize a program (every attempt failed against the real COBOL), the
 * pipeline pauses that program in needs_review and this readout asks a person what it is missing
 * (pipeline/graph.py needs_review; POST /api/runs/<session>/feedback in tools/serve.py). The
 * feedback is added to the spec for 2 more attempts. It only guides the rewrite: acceptance still
 * needs every golden case to match the real COBOL. Recordings show nothing here. */
(() => {
  const POLL_MS = 1500, MAX = 500;
  const style = document.createElement('style');
  style.textContent = `
  .hint { position: fixed; right: 24px; bottom: 52px; z-index: 4; width: min(380px, calc(100vw - 48px)); box-sizing: border-box;
    display: flex; flex-direction: column; gap: 12px; padding: 18px 20px 16px; font-family: var(--mono);
    background: rgba(6,5,13,.9); box-shadow: 0 0 22px 8px rgba(6,5,13,.75);
    border-top: 1px solid rgba(232,234,242,.12); transition: border-color .4s; }
  .hint.ask { border-top-color: rgba(255,184,203,.75); }
  .hint[hidden], .hint [hidden], body.intake-on .hint, .hint.under-panel { display: none; }
  .hint-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
  .hint-title { font-size: 9.5px; letter-spacing: 3.5px; text-transform: uppercase; color: rgba(242,241,248,.85); }
  .hint-state { font-size: 9px; letter-spacing: 2.5px; text-transform: uppercase; color: rgba(232,234,242,.4); text-align: right; }
  .hint.ask .hint-state { color: #ffb8cb; text-shadow: 0 0 10px rgba(255,140,175,.45); }
  .hint-why { font: 400 13px/1.5 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; color: rgba(232,234,242,.72); }
  .hint-why:empty { display: none; }
  .hint-case { font-size: 11px; line-height: 1.7; color: rgba(232,234,242,.5); white-space: pre; overflow-x: auto; }
  .hint-case b { font-weight: 400; color: #ffc7d5; }
  .hint-case:empty { display: none; }
  .hint textarea { resize: none; box-sizing: border-box; width: 100%; min-height: 62px; background: rgba(232,234,242,.03); border: 0;
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
  .hint-log .ok b { color: #b9f0dc; }
  .hint-log .bad b { color: #ffb8cb; }
  .hint-log .working b { color: #d4c4ff; }`;
  document.head.appendChild(style);

  const box = document.createElement('section');
  box.className = 'hint'; box.hidden = true; box.setAttribute('aria-label', 'Help the agent');
  box.innerHTML = `
    <div class="hint-head"><span class="hint-title" id="hint-title">Needs a person</span><span class="hint-state" id="hint-state"></span></div>
    <div class="hint-why" id="hint-why"></div>
    <div class="hint-case" id="hint-case"></div>
    <textarea id="hint-note" maxlength="${MAX}" aria-label="Your feedback"
      placeholder="What is the agent missing? e.g. fees are cut off at the cent, never rounded"></textarea>
    <div class="hint-act"><button id="hint-send">Send feedback</button><span class="hint-msg" id="hint-msg" role="status"></span></div>
    <ol class="hint-log" id="hint-log"></ol>`;
  document.body.appendChild(box);
  const $ = id => document.getElementById(id);
  const titleEl = $('hint-title'), stateEl = $('hint-state'), whyEl = $('hint-why'), caseEl = $('hint-case'),
        note = $('hint-note'), sendBtn = $('hint-send'), msg = $('hint-msg'), log = $('hint-log'), panel = $('panel');

  let session = null, rep = null, asking = null, sending = false;
  const upper = s => String(s || '').toUpperCase();

  note.addEventListener('keydown', e => {
    e.stopPropagation();  // typing must never drive the galaxy's keyboard shortcuts
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    if (e.key === 'Escape') note.blur();
  });
  sendBtn.onclick = send;

  // seconds left in the module's review window, from its latest needs_review event
  function secondsLeft(m) {
    const evs = (rep.events || []).filter(e => e.module === m.id && e.node === 'needs_review');
    const last = evs[evs.length - 1], secs = last && +((/up to ([\d.]+)s/.exec(last.msg || '') || [])[1] || 0);
    return secs ? Math.max(0, Math.round(secs - (Date.now() - new Date(last.t)) / 1000)) : null;
  }

  function render() {
    const mods = rep.modules || [];
    const stuck = rep.finished ? null : mods.find(m => m.status === 'needs_review');
    const helped = mods.filter(m => (m.human_hints || []).length);
    box.hidden = !stuck && !helped.length;
    if (box.hidden) return;
    if ((stuck && stuck.id) !== asking) { asking = stuck && stuck.id; note.value = ''; say(''); }
    box.classList.toggle('ask', !!stuck);
    for (const el of [note, sendBtn.parentElement]) el.hidden = !stuck;

    if (stuck) {
      const hist = stuck.history || [], h = hist[hist.length - 1] || {}, ex = h.explanation || {};
      const f = (h.failures || [])[0], left = secondsLeft(stuck);
      titleEl.textContent = 'Needs a person';
      stateEl.textContent = left === null ? 'waiting' : `waiting · ${left}s`;
      whyEl.textContent = `The agent could not modernize ${upper(stuck.id)}: after ${stuck.attempts} attempts it matches `
        + `${h.passed} of ${h.total} cases.` + (ex.reason ? ` Why: ${ex.reason}` : '') + ' What is it missing?';
      caseEl.replaceChildren();
      if (f) {
        const row = (label, value, bad) => { const b = document.createElement(bad ? 'b' : 'span'); b.textContent = `${label.padEnd(8)}${value}\n`; return b; };
        caseEl.append(row('input', f.input), row('cobol', f.expected), row('python', f.actual, true));
      }
    } else {
      const working = helped.some(m => m.status !== 'done' && m.status !== 'failed');
      titleEl.textContent = 'Human feedback';
      stateEl.textContent = working ? 'agent retrying' : rep.finished ? 'run finished' : '';
      whyEl.textContent = working ? 'The agent is rewriting with your feedback. It still has to match the real COBOL on every case.' : '';
      caseEl.replaceChildren();
    }

    log.replaceChildren(...helped.flatMap(m => m.human_hints.map((h, i, all) => {
      const last = i === all.length - 1;
      const kind = !last ? 'bad' : m.status === 'done' ? 'ok' : m.status === 'failed' ? 'bad' : 'working';
      const label = kind === 'ok' ? `${m.id} · verified after attempt ${m.attempts}`
        : kind === 'working' ? `${m.id} · attempt ${m.attempts}` : `${m.id} · not enough`;
      return item(kind, label, h.note);
    })));
  }

  function item(kind, label, text) {
    const li = document.createElement('li'), b = document.createElement('b');
    li.className = kind; b.textContent = label; li.append(b, text);
    return li;
  }

  async function send() {
    const text = note.value.split(/\s+/).filter(Boolean).join(' ').slice(0, MAX);
    if (sending || !session || !asking) return;
    if (!text) { say('Write your feedback first.', true); return; }
    sending = true; sendBtn.disabled = true;
    try {
      const r = await fetch(`api/runs/${session}/feedback`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ module: asking, note: text }) });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
      note.value = '';
      say(`Sent. ${upper(asking)} gets 2 more attempts.`);
    } catch (err) {
      say(err.message, true);
    } finally {
      sending = false; sendBtn.disabled = false;
    }
  }

  function say(text, bad = false) { msg.textContent = text; msg.classList.toggle('bad', bad); }

  async function poll() {
    const m = /^#live=([0-9a-z-]+)$/.exec(location.hash);
    if (!m) { box.hidden = true; session = rep = asking = null; return setTimeout(poll, POLL_MS); }
    if (m[1] !== session) { session = m[1]; rep = asking = null; say(''); }
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
