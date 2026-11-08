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
  /* Needs a person: a band across the top of the sky, fading into it. No box, no edges.
     Three columns: what is wrong · the failing case · your prompt. */
  .hint { position: fixed; z-index: 4; left: 0; right: 0; top: 0; box-sizing: border-box; font-family: var(--mono); }
  .hint-shade { position: fixed; left: 0; right: 0; top: 0; height: 330px; z-index: 3; pointer-events: none; opacity: 0; transition: opacity .7s ease, height .5s ease;
    background: linear-gradient(180deg, rgba(4,3,10,.96) 0%, rgba(4,3,10,.9) 55%, rgba(4,3,10,.5) 78%, rgba(4,3,10,0) 100%); }
  .hint-shade.on { opacity: 1; } .hint-shade.thin { height: 130px; }
  body.intake-on .hint-shade { opacity: 0; }
  .hint[hidden], .hint [hidden], body.intake-on .hint, .hint.under-panel { display: none; }
  .hint.ask { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, .8fr) minmax(0, 1.15fr); column-gap: 52px; row-gap: 10px;
    align-content: start; padding: 30px 48px 0; animation: hint-drop .75s cubic-bezier(.2,.75,.2,1); }
  .hint.ask .hint-head { grid-column: 1; grid-row: 1; }
  .hint.ask .hint-why { grid-column: 1; grid-row: 2; }
  .hint.ask .hint-sub { grid-column: 1; grid-row: 3; }
  .hint.ask .hint-case { grid-column: 2; grid-row: 1 / span 3; align-self: start; margin-top: 22px; }
  .hint.ask .hint-ask-l { grid-column: 3; grid-row: 1; }
  .hint.ask .hint-field { grid-column: 3; grid-row: 2; }
  .hint.ask .hint-act { grid-column: 3; grid-row: 3; }
  .hint.ask .hint-log { display: none; }
  .hint.quiet { display: flex; align-items: baseline; gap: 26px; padding: 26px 48px 0; animation: hint-in .6s ease; }
  @keyframes hint-drop { from { opacity: 0; transform: translateY(-28px); } to { opacity: 1; transform: none; } }
  @keyframes hint-in { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: none; } }
  .hint-head { display: flex; align-items: baseline; gap: 18px; white-space: nowrap; }
  .hint-title { font-size: 10px; letter-spacing: 5px; text-transform: uppercase; color: rgba(242,241,248,.92); }
  .hint-state { display: inline-flex; align-items: center; gap: 8px; font-size: 9px; letter-spacing: 3px; text-transform: uppercase; color: rgba(232,234,242,.42); }
  .hint-state::before { content: ''; width: 4px; height: 4px; border-radius: 50%; background: currentColor; box-shadow: 0 0 7px currentColor; }
  .hint.ask .hint-state { color: #ffb8cb; } .hint.ask .hint-state::before { animation: hint-pulse 1.4s ease-in-out infinite; }
  .hint.sent .hint-state, .hint.done .hint-state { color: #b9f0dc; } .hint.sent .hint-state::before { animation: none; }
  .hint.quiet .hint-state { color: #d4c4ff; }
  @keyframes hint-pulse { 50% { opacity: .25; } }
  .hint-why { font: 400 17px/1.45 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; color: rgba(244,243,250,.95); }
  .hint-sub { font: 400 12.5px/1.55 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; color: rgba(232,234,242,.52); }
  .hint-why:empty, .hint-sub:empty, .hint-case:empty { display: none; }
  .hint-case { display: grid; grid-template-columns: max-content 1fr; gap: 6px 22px; }
  .hc-l { font-size: 9px; letter-spacing: 3px; text-transform: uppercase; color: rgba(232,234,242,.36); padding-top: 3px; }
  .hc-v { font-size: 13px; line-height: 1.5; white-space: pre; color: rgba(232,234,242,.62); }
  .hc-bad { color: #ffd6e1; text-shadow: 1.2px 0 rgba(120,220,255,.5), -1.2px 0 rgba(255,120,170,.6); }
  .hint-ask-l { display: flex; justify-content: space-between; gap: 16px; font-size: 9px; letter-spacing: 3px; text-transform: uppercase; color: rgba(212,196,255,.85); padding-top: 1px; }
  .hint-keys { color: rgba(232,234,242,.3); }
  .hint.sent .hint-keys { visibility: hidden; }
  /* your prompt: lavender, on one hairline, with a prompt mark; what you read stays grey and white */
  .hint-field { position: relative; }
  .hint-field::before { content: '›'; position: absolute; left: 0; top: 3px; font: 300 19px/1.4 var(--mono); color: #d4c4ff; pointer-events: none; }
  .hint textarea { display: block; resize: none; box-sizing: border-box; width: 100%; min-height: 76px; outline: none; border: 0; background: none;
    border-bottom: 1px solid rgba(212,196,255,.4); padding: 4px 0 10px 24px; color: #e9e2ff; caret-color: #d4c4ff;
    font: 400 16.5px/1.5 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; text-shadow: 0 0 16px rgba(200,180,255,.25); }
  .hint textarea:focus { border-bottom-color: #d4c4ff; }
  .hint textarea::placeholder { color: rgba(212,196,255,.32); text-shadow: none; }
  .hint.sent textarea { color: rgba(220,245,236,.8); border-bottom-color: rgba(185,240,220,.5); }
  .hint.sent .hint-field::before { color: #b9f0dc; }
  .hint-act { display: flex; align-items: baseline; gap: 18px; }
  .hint-act button { background: none; border: 0; padding: 4px 0; cursor: pointer; font: 9.5px var(--mono); letter-spacing: 3.5px; text-transform: uppercase;
    color: #d4c4ff; display: inline-flex; align-items: center; gap: 8px; flex: none; }
  .hint-act button::before { content: ''; width: 4px; height: 4px; border-radius: 50%; background: currentColor; box-shadow: 0 0 6px currentColor; }
  .hint-act button:hover { color: #efe9ff; }
  .hint-act button[disabled] { opacity: .3; cursor: default; }
  .hint-msg { font-size: 9.5px; letter-spacing: 3px; text-transform: uppercase; color: rgba(232,234,242,.45); }
  .hint-msg.ok { color: #b9f0dc; text-shadow: 0 0 10px rgba(150,240,210,.4); }
  .hint-msg.bad { color: #ffb8cb; }
  .hint-log { list-style: none; margin: 0; padding: 0; min-width: 0; flex: 1; }
  .hint-log li { display: flex; align-items: baseline; gap: 18px; min-width: 0; font: 300 14px/1.5 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Arial, sans-serif; color: rgba(236,234,246,.8); }
  .hint-log li span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .hint-log b { flex: none; font: 9px var(--mono); letter-spacing: 3px; text-transform: uppercase; font-weight: 400; color: rgba(232,234,242,.4); }
  .hint-log .ok b { color: #b9f0dc; } .hint-log .bad b { color: #ffb8cb; } .hint-log .working b { color: #d4c4ff; }
  .hint.quiet .hint-why { font-size: 12.5px; color: rgba(232,234,242,.55); }
  @media (max-width: 980px) {
    .hint.ask { grid-template-columns: 1fr; padding: 20px 20px 0; row-gap: 8px; }
    .hint.ask > * { grid-column: 1 !important; grid-row: auto !important; } .hint.ask .hint-case { margin-top: 4px; }
    .hint-shade { height: 560px; } .hint.quiet { padding: 18px 20px 0; flex-wrap: wrap; gap: 8px 18px; } }
  @media (prefers-reduced-motion: reduce) { .hint, .hint.ask .hint-state::before { animation: none; } }`;
  document.head.appendChild(style);

  const box = document.createElement('section');
  box.className = 'hint'; box.hidden = true; box.setAttribute('aria-label', 'Help the agent');
  box.innerHTML = `
    <div class="hint-head"><span class="hint-title" id="hint-title">Needs a person</span><span class="hint-state" id="hint-state"></span></div>
    <div class="hint-why" id="hint-why"></div>
    <div class="hint-sub" id="hint-sub"></div>
    <div class="hint-case" id="hint-case"></div>
    <div class="hint-ask-l" id="hint-ask-l"><span>Your prompt</span><span class="hint-keys">Enter ↵ to send</span></div>
    <div class="hint-field"><textarea id="hint-note" maxlength="${MAX}" aria-label="Your feedback"
      placeholder="Type what the agent is missing, then press Enter"></textarea></div>
    <div class="hint-act"><button id="hint-send">Send feedback</button><span class="hint-msg" id="hint-msg" role="status"></span></div>
    <ol class="hint-log" id="hint-log"></ol>`;
  document.body.appendChild(box);
  const shade = document.createElement('div'); shade.className = 'hint-shade'; shade.setAttribute('aria-hidden', 'true');
  document.body.appendChild(shade);
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
  function mode(kind) {  // ask: drops in from the top over a darker sky; quiet: a small note at the top left
    box.classList.toggle('ask', kind === 'ask'); box.classList.toggle('quiet', kind !== 'ask');
    shade.classList.toggle('on', true); shade.classList.toggle('thin', kind !== 'ask');
    for (const el of [note.parentElement, sendBtn.parentElement, askL]) el.hidden = kind !== 'ask';
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
    const t = document.createElement('span'); t.textContent = text; t.title = text;
    li.className = kind; b.textContent = label; li.append(b, t);
    return li;
  }

  async function send() {
    const text = note.value.split(/\s+/).filter(Boolean).join(' ').slice(0, MAX);
    if (!session && replayAsk) {  // a recording: the presenter's hint releases the run's real fix
      if (!text) { say('Type the hint first, or press Tab for the one this run used.', true); return; }
      note.readOnly = true; galaxy.sendHint(text); return;
    }
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

  // ---------- a recording: the presenter types the hint, and the run's real fix plays ----------
  // The replay waits at "Needs a person" until the presenter sends a hint (Enter, or Next sends the
  // run's own). What follows is the recorded run: the attempt that used the hint the person really sent.
  let replayAsk = null;  // the ask stop the presenter is typing at
  function replayStep() {
    const v = window.galaxy && galaxy.view && galaxy.view(), b = v && v.beat;
    const m = b && b.mi !== undefined ? v.R.modules[b.mi] : null;
    const full = m && (v.full.modules || []).find(q => q.id === m.id);
    const hint = full && (full.human_hints || [])[0];
    if (!hint) { box.hidden = true; replayAsk = null; return; }
    const reviewedAt = hint.attempt - 2;  // the failed attempt that made it ask (history index)
    const stop = v.TL.beats.find(q => q.mi === b.mi && q.review);  // the stop where it asked a person
    const inReview = !!stop && b === stop;
    const retrying = !!stop && !inReview && b.mi === stop.mi && b.k !== 'swoop' && b.t0 >= stop.t1 - 1e-6;
    if (!inReview && !retrying) { box.hidden = true; replayAsk = null; return; }
    box.hidden = false;
    const hist = full.history || [], h = hist[reviewedAt] || {}, ex = h.explanation || {}, f = (h.failures || [])[0];
    if (inReview) {
      const live = v.sim && stop.working;  // the presenter is at the ask now: they type
      const sent = live ? v.hintSent : true;
      mode('ask'); box.classList.toggle('sent', sent); box.classList.remove('done');
      titleEl.textContent = `Needs a person  ·  ${upper(m.id)}`;
      stateEl.textContent = sent ? 'feedback sent' : 'waiting for you';
      whyEl.textContent = `${upper(m.id)} still doesn't match the real COBOL: ${h.passed} of ${h.total} cases after ${hint.attempt - 1} attempt${hint.attempt > 2 ? 's' : ''}.`;
      subEl.textContent = ex.reason ? `Why: ${ex.reason}` : '';
      if (replayAsk !== stop) {  // arrived at the ask: a clean prompt, ready to type into
        replayAsk = stop; showCase(f); log.replaceChildren(); say('');
        note.value = live ? '' : hint.note;
        if (live) setTimeout(() => { if (replayAsk === stop && !note.readOnly) note.focus({ preventScroll: true }); }, 350);
      }
      note.readOnly = sent; sendBtn.disabled = sent;
      if (sent && !live) note.value = hint.note;
      if (sent && live && !note.value) note.value = v.typedHint || hint.note;  // Next sent the run's own hint
      if (sent) { say(`Sent  ·  ${upper(m.id)} gets 2 more attempts`); msg.classList.add('ok'); }
    } else {
      replayAsk = null;
      const done = b.at === 6 && m.status === 'done';
      mode('quiet'); box.classList.remove('sent'); box.classList.toggle('done', done);
      titleEl.textContent = 'Human feedback';
      stateEl.textContent = done ? 'verified' : 'agent retrying';
      whyEl.textContent = '';
      subEl.textContent = ''; caseEl.replaceChildren();
      log.replaceChildren(item(done ? 'ok' : 'working', done ? `${m.id} · verified after attempt ${hint.attempt} · hint in this run` : `${m.id} · attempt ${hint.attempt} · hint in this run`, hint.note));
    }
  }
  // Tab at the ask fills in the hint the person sent in this run (a presenter's shortcut)
  note.addEventListener('keydown', e => {
    if (e.key !== 'Tab' || session || !replayAsk || note.readOnly) return;
    const v = galaxy.view(), m = v && v.R.modules[replayAsk.mi], full = m && v.full.modules.find(q => q.id === m.id);
    const hint = full && (full.human_hints || [])[0];
    if (hint) { e.preventDefault(); note.value = hint.note; }
  });

  async function poll() {
    const m = /^#live=([0-9a-z-]+)$/.exec(location.hash);
    if (!m) {
      session = rep = asking = null;
      try { replayStep(); } catch (err) { box.hidden = true; }
      place();
      return setTimeout(poll, 80);
    }
    note.readOnly = false; sendBtn.disabled = sending; replayAsk = null;
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
    shade.classList.toggle('on', !box.hidden && !box.classList.contains('under-panel'));
    // sit above the toolbar and the canvas's LIVE label, however many lines the toolbar wraps to
    const bar = document.querySelector('.controls');
    box.style.bottom = '';
  }
  poll();
})();
