/* Human feedback (live runs only). Owner: Hemant.
 * When the agent cannot modernize a program (every attempt failed against the real COBOL), the
 * pipeline pauses that program in needs_review and this readout asks a person what it is missing
 * (pipeline/graph.py needs_review; POST /api/runs/<session>/feedback in tools/serve.py). The
 * feedback is added to the spec for 2 more attempts. It only guides the rewrite: acceptance still
 * needs every golden case to match the real COBOL. A recording that includes a person's hint replays
 * that moment here from what was recorded (replayStep): the ask, the real hint typing in, and the
 * retry, timed by the galaxy's clock so Pause, Next and Back stay in step. */
(() => {
  const POLL_MS = 1500, MAX = 500;
  const style = document.createElement('style');
  style.textContent = `
  /* No box: the question, the failing case and the hint are written onto the sky, like a station caption. */
  .hint { position: fixed; z-index: 4; box-sizing: border-box; display: flex; flex-direction: column; gap: 14px; font-family: var(--mono);
    animation: hint-in .7s cubic-bezier(.2,.7,.2,1); }
  .hint.ask { left: 47vw; top: 13vh; width: min(560px, 47vw); }
  .hint.quiet { right: 28px; width: min(420px, 38vw); gap: 8px; }
  .hint.ask::before { content: ''; position: absolute; inset: -70px -90px -60px -90px; z-index: -1; pointer-events: none;
    background: radial-gradient(ellipse at 42% 45%, rgba(6,5,13,.74), rgba(6,5,13,.4) 45%, rgba(6,5,13,0) 72%); }
  @keyframes hint-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  .hint[hidden], .hint [hidden], body.intake-on .hint, .hint.under-panel { display: none; }
  .hint-head { display: flex; align-items: baseline; gap: 18px; }
  .hint-title { font-size: 10px; letter-spacing: 5px; text-transform: uppercase; color: rgba(242,241,248,.9); }
  .hint-state { display: inline-flex; align-items: center; gap: 8px; font-size: 9px; letter-spacing: 3px; text-transform: uppercase; color: rgba(232,234,242,.42); }
  .hint-state::before { content: ''; width: 4px; height: 4px; border-radius: 50%; background: currentColor; box-shadow: 0 0 7px currentColor; }
  .hint.ask .hint-state { color: #ffb8cb; } .hint.ask .hint-state::before { animation: hint-pulse 1.4s ease-in-out infinite; }
  .hint.sent .hint-state, .hint.done .hint-state { color: #b9f0dc; } .hint.sent .hint-state::before { animation: none; }
  @keyframes hint-pulse { 50% { opacity: .25; } }
  .hint-why { font: 400 21px/1.42 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; color: rgba(244,243,250,.95); letter-spacing: -.1px; }
  .hint.quiet .hint-why { font-size: 12.5px; color: rgba(232,234,242,.6); }
  .hint-sub { font: 400 13.5px/1.55 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; color: rgba(232,234,242,.58); }
  .hint-why:empty, .hint-sub:empty, .hint-case:empty { display: none; }
  .hint-case { display: grid; grid-template-columns: max-content 1fr; gap: 7px 26px; margin: 4px 0 2px; }
  .hc-l { font-size: 9px; letter-spacing: 3px; text-transform: uppercase; color: rgba(232,234,242,.38); padding-top: 5px; }
  .hc-v { font-size: 15px; line-height: 1.5; white-space: pre; color: rgba(232,234,242,.62); }
  .hc-bad { color: #ffd6e1; text-shadow: 1.2px 0 rgba(120,220,255,.5), -1.2px 0 rgba(255,120,170,.6); }
  .hint-ask-l { font-size: 9px; letter-spacing: 3px; text-transform: uppercase; color: rgba(212,196,255,.75); margin-top: 6px; }
  .hint textarea { resize: none; box-sizing: border-box; width: 100%; min-height: 136px; background: none; border: 0; outline: none; padding: 4px 0 10px;
    border-bottom: 1px solid rgba(232,234,242,.16); color: #f4f2fb; caret-color: #d4c4ff;
    font: 300 19px/1.5 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; text-shadow: 0 0 18px rgba(200,180,255,.18); }
  .hint textarea:focus { border-bottom-color: rgba(212,196,255,.6); }
  .hint textarea::placeholder { color: rgba(232,234,242,.24); }
  .hint-act { display: flex; align-items: baseline; gap: 18px; }
  .hint-act button { background: none; border: 0; padding: 4px 0; cursor: pointer; font: 9.5px var(--mono); letter-spacing: 3.5px; text-transform: uppercase;
    color: #d4c4ff; display: inline-flex; align-items: center; gap: 8px; flex: none; }
  .hint-act button::before { content: ''; width: 4px; height: 4px; border-radius: 50%; background: currentColor; box-shadow: 0 0 6px currentColor; }
  .hint-act button:hover { color: #efe9ff; }
  .hint-act button[disabled] { opacity: .35; cursor: default; }
  .hint.sent .hint-act button { opacity: .25; }
  .hint-msg { font-size: 9.5px; letter-spacing: 3px; text-transform: uppercase; color: rgba(232,234,242,.45); }
  .hint-msg.ok { color: #b9f0dc; text-shadow: 0 0 10px rgba(150,240,210,.4); }
  .hint-msg.bad { color: #ffb8cb; }
  .hint-log { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; max-height: 140px; overflow: auto; }
  .hint-log li { font: 300 14px/1.5 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; color: rgba(236,234,246,.82); }
  .hint-log li::before { content: ''; display: block; width: 22px; height: 1px; margin: 0 0 8px; background: linear-gradient(90deg, rgba(212,196,255,.8), rgba(212,196,255,0)); }
  .hint-log b { display: block; margin-bottom: 4px; font: 9px var(--mono); letter-spacing: 3px; text-transform: uppercase; font-weight: 400; color: rgba(232,234,242,.4); }
  .hint-log .ok b { color: #b9f0dc; }
  .hint-log .bad b { color: #ffb8cb; }
  .hint-log .working b { color: #d4c4ff; }
  @media (max-width: 760px) { .hint.ask, .hint.quiet { left: 16px; right: 16px; width: auto; top: auto; } .hint-why { font-size: 17px; } }
  @media (prefers-reduced-motion: reduce) { .hint, .hint.ask .hint-state::before { animation: none; } }`;
  document.head.appendChild(style);

  const box = document.createElement('section');
  box.className = 'hint'; box.hidden = true; box.setAttribute('aria-label', 'Help the agent');
  box.innerHTML = `
    <div class="hint-head"><span class="hint-title" id="hint-title">Needs a person</span><span class="hint-state" id="hint-state"></span></div>
    <div class="hint-why" id="hint-why"></div>
    <div class="hint-sub" id="hint-sub"></div>
    <div class="hint-case" id="hint-case"></div>
    <div class="hint-ask-l" id="hint-ask-l">What is the agent missing?</div>
    <textarea id="hint-note" maxlength="${MAX}" aria-label="Your feedback"
      placeholder="What is the agent missing? e.g. fees are cut off at the cent, never rounded"></textarea>
    <div class="hint-act"><button id="hint-send">Send feedback</button><span class="hint-msg" id="hint-msg" role="status"></span></div>
    <ol class="hint-log" id="hint-log"></ol>`;
  document.body.appendChild(box);
  const $ = id => document.getElementById(id);
  const titleEl = $('hint-title'), stateEl = $('hint-state'), whyEl = $('hint-why'), caseEl = $('hint-case'),
        note = $('hint-note'), subEl = $('hint-sub'), askL = $('hint-ask-l'), sendBtn = $('hint-send'), msg = $('hint-msg'), log = $('hint-log'), panel = $('panel');

  let session = null, rep = null, asking = null, sending = false, sentTo = null;  // sentTo: feedback sent, not yet used
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

  // the failing case, laid out like the Verify caption: input, what the COBOL printed, what the rewrite printed
  function showCase(f) {
    caseEl.replaceChildren();
    if (!f) return;
    for (const [label, value, bad] of [['input', f.input], ['cobol', f.expected], ['rewrite', f.actual, true]]) {
      const l = document.createElement('span'), v = document.createElement('span');
      l.className = 'hc-l'; l.textContent = label; v.className = 'hc-v' + (bad ? ' hc-bad' : ''); v.textContent = String(value);
      caseEl.append(l, v);
    }
  }
  function mode(kind) {  // ask: a big question in the caption's place; quiet: a small note above the toolbar
    box.classList.toggle('ask', kind === 'ask'); box.classList.toggle('quiet', kind !== 'ask');
    for (const el of [note, sendBtn.parentElement, askL]) el.hidden = kind !== 'ask';
  }

  function render() {
    const mods = rep.modules || [];
    const stuck = rep.finished ? null : mods.find(m => m.status === 'needs_review');
    const helped = mods.filter(m => (m.human_hints || []).length);
    const pending = !stuck && mods.find(m => m.id === sentTo && !(m.human_hints || []).length
                                         && m.status !== 'done' && m.status !== 'failed');
    box.hidden = !stuck && !helped.length && !pending;
    if (box.hidden) return;
    if ((stuck && stuck.id) !== asking) { asking = stuck && stuck.id; note.value = ''; say(''); }
    mode(stuck ? 'ask' : 'quiet'); box.classList.remove('sent', 'done');

    if (stuck) {
      const hist = stuck.history || [], h = hist[hist.length - 1] || {}, ex = h.explanation || {};
      const f = (h.failures || [])[0], left = secondsLeft(stuck);
      titleEl.textContent = `Needs a person  ·  ${upper(stuck.id)}`;
      stateEl.textContent = left === null ? 'waiting' : `waiting · ${left}s`;
      whyEl.textContent = `${upper(stuck.id)} still doesn't match the real COBOL: ${h.passed} of ${h.total} cases after ${stuck.attempts} attempt${stuck.attempts > 1 ? 's' : ''}.`;
      subEl.textContent = ex.reason ? `Why: ${ex.reason}` : '';
      showCase(f);
    } else {
      const working = !!pending || helped.some(m => m.status !== 'done' && m.status !== 'failed');
      titleEl.textContent = 'Human feedback';
      stateEl.textContent = working ? 'agent retrying' : rep.finished ? 'run finished' : '';
      whyEl.textContent = working ? 'The agent is rewriting with your feedback. It still has to match the real COBOL on every case.' : '';
      subEl.textContent = ''; caseEl.replaceChildren();
    }

    log.replaceChildren(...helped.flatMap(m => m.human_hints.map((h, i, all) => {
      const last = i === all.length - 1;
      const kind = !last || m === stuck ? 'bad' : m.status === 'done' ? 'ok' : m.status === 'failed' ? 'bad' : 'working';
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
      note.value = ''; sentTo = asking;
      say(`Sent  ·  ${upper(asking)} gets 2 more attempts`); msg.classList.add('ok');
    } catch (err) {
      say(err.message, true);
    } finally {
      sending = false; sendBtn.disabled = false;
    }
  }

  function say(text, bad = false) { msg.textContent = text; msg.classList.toggle('bad', bad); if (bad) msg.classList.remove('ok'); }

  // ---------- a recording: replay the person's hint exactly as it happened ----------
  const TYPE_FROM = 1.4, TYPE_CPS = 48, SENT_AFTER = .5;  // seconds into the stop; characters per second
  function replayStep() {
    const v = window.galaxy && galaxy.view && galaxy.view(), b = v && v.beat;
    const m = b && b.mi !== undefined ? v.R.modules[b.mi] : null;
    const full = m && (v.full.modules || []).find(q => q.id === m.id);
    const hint = full && (full.human_hints || [])[0];
    if (!hint) { box.hidden = true; return; }
    const reviewedAt = hint.attempt - 2;  // the failed attempt that made it ask (history index)
    const stop = v.TL.beats.find(q => q.mi === b.mi && q.review);  // the stop where it asked a person
    const inReview = !!stop && b === stop;
    const retrying = !!stop && !inReview && b.mi === stop.mi && b.k !== 'swoop' && b.t0 >= stop.t1 - 1e-6;
    if (!inReview && !retrying) { box.hidden = true; return; }
    box.hidden = false; note.readOnly = true; sendBtn.disabled = true;
    const hist = full.history || [], h = hist[reviewedAt] || {}, ex = h.explanation || {}, f = (h.failures || [])[0];
    if (inReview) {
      const t = v.clock - b.t0, typed = Math.max(0, Math.min(hint.note.length, Math.floor((t - TYPE_FROM) * TYPE_CPS)));
      const sent = typed >= hint.note.length && t > TYPE_FROM + hint.note.length / TYPE_CPS + SENT_AFTER;
      mode('ask'); box.classList.toggle('sent', sent); box.classList.remove('done');
      titleEl.textContent = `Needs a person  ·  ${upper(m.id)}`;
      stateEl.textContent = sent ? 'feedback sent' : 'waiting';
      whyEl.textContent = `${upper(m.id)} still doesn't match the real COBOL: ${h.passed} of ${h.total} cases after ${hint.attempt - 1} attempt${hint.attempt > 2 ? 's' : ''}.`;
      subEl.textContent = ex.reason ? `Why: ${ex.reason}` : '';
      showCase(f);
      const cursor = !sent && Math.floor(v.clock * 2.2) % 2 === 0 ? '▍' : '';
      note.value = hint.note.slice(0, typed) + cursor;
      note.scrollTop = note.scrollHeight;
      msg.classList.toggle('ok', sent);
      say(sent ? `Sent  ·  ${upper(m.id)} gets 2 more attempts` : '');
      msg.classList.toggle('ok', sent);
      log.replaceChildren();
    } else {
      const done = b.at === 6 && m.status === 'done';
      mode('quiet'); box.classList.remove('sent'); box.classList.toggle('done', done);
      titleEl.textContent = 'Human feedback';
      stateEl.textContent = done ? 'verified' : 'agent retrying';
      whyEl.textContent = done ? '' : 'Rewriting with the person\'s feedback. It still has to match the real COBOL on every case.';
      subEl.textContent = ''; caseEl.replaceChildren();
      log.replaceChildren(item(done ? 'ok' : 'working', done ? `${m.id} · verified after attempt ${hint.attempt}` : `${m.id} · attempt ${hint.attempt}`, hint.note));
    }
  }

  async function poll() {
    const m = /^#live=([0-9a-z-]+)$/.exec(location.hash);
    if (!m) {
      session = rep = asking = null;
      if (note.readOnly === false && !box.hidden) box.hidden = true;
      try { replayStep(); } catch (err) { box.hidden = true; }
      place();
      return setTimeout(poll, 80);
    }
    note.readOnly = false; sendBtn.disabled = sending;
    if (m[1] !== session) { session = m[1]; rep = asking = sentTo = null; say(''); }
    try {
      const r = await fetch(`api/runs/${session}/replay`, { cache: 'no-store' });
      if (r.status === 200) { rep = await r.json(); render(); }
    } catch (err) { /* the galaxy already reports a lost run */ }
    place();
    setTimeout(poll, POLL_MS);
  }
  function place() {
    box.classList.toggle('under-panel', !!(panel && panel.classList.contains('open')));
    // sit above the toolbar and the canvas's LIVE label, however many lines the toolbar wraps to
    const bar = document.querySelector('.controls');
    box.style.bottom = box.classList.contains('quiet') && bar ? `${Math.max(52, innerHeight - bar.getBoundingClientRect().top + 44)}px` : '';
  }
  poll();
})();
