/* Legacy → Verified: replays a recorded run as a star travelling through the pipeline.
   Everything on screen comes from web/replays/<name>.json (exported by tools/export_replay.py).
   Black and white is old COBOL; colour (aurora) arrives as the program becomes verified Python. */
(() => {
  'use strict';
  const cv = document.getElementById('sky'), x = cv.getContext('2d');
  const MONO = 'ui-monospace, "SF Mono", Menlo, Consolas, monospace';
  const BASE_H = 520, GAP = 560, CY = 252;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let W = 0, H = BASE_H, K = 1, DPR = 1;

  function resize() {
    if (innerWidth < 2 || innerHeight < 2) return false;  // hidden or collapsed window: keep the last size
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    K = innerHeight / BASE_H; W = innerWidth / K; H = BASE_H;
    cv.width = innerWidth * DPR; cv.height = innerHeight * DPR;
    x.setTransform(DPR * K, 0, 0, DPR * K, 0, 0);
    aur.width = Math.ceil(innerWidth / 3); aur.height = Math.ceil(innerHeight / 3);
    return true;
  }

  const STATIONS = [
    ['01', 'Discover'], ['02', 'Read'], ['03', 'Probe'], ['04', 'Record'],
    ['05', 'Rewrite'], ['06', 'Verify'], ['07', 'Verified']];

  // ---------- helpers ----------
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const ease = u => u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
  const mix = (a, b, f) => a.map((v, i) => Math.round(v + (b[i] - v) * f));
  const rgb = a => a.join(',');
  function setLS(v) { if ('letterSpacing' in x) x.letterSpacing = v + 'px'; }
  function txt(s, px, py, sz, a, ls = 0, al = 'center', col = '232,234,242', wt = '') {
    x.font = `${wt} ${sz}px ${MONO}`; x.fillStyle = `rgba(${col},${a})`; x.textAlign = al;
    setLS(ls); x.fillText(s, px, py); setLS(0);
  }
  function measure(s, sz, ls = 0, wt = '') { x.font = `${wt} ${sz}px ${MONO}`; setLS(ls); const w = x.measureText(s).width; setLS(0); return w; }
  function wrap(s, max, sz, ls) {
    const words = String(s).split(/\s+/), lines = []; let cur = '';
    for (const w of words) { const t = cur ? cur + ' ' + w : w; if (measure(t, sz, ls) > max && cur) { lines.push(cur); cur = w; } else cur = t; }
    if (cur) lines.push(cur); return lines;
  }
  const clip = (s, n) => (s = String(s || '')).length > n ? s.slice(0, n - 1) + '…' : s;

  // ---------- static layers ----------
  function blurLayer(w, h, n, fn) {
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    const f = c.getContext('2d'); f.filter = 'blur(30px)'; for (let i = 0; i < n; i++) fn(f, i); return c;
  }
  const seeds = Array.from({ length: 100 }, () => [Math.random(), Math.random(), Math.random(), Math.random(), Math.random()]);
  const band = col => blurLayer(2400, BASE_H, 100, (f, i) => {
    const [u, a, b, c2, d] = seeds[i]; f.fillStyle = col(b, c2, d);
    for (const dx of [-2400, 0, 2400]) {  // wrap copies so the tile repeats with no seam
      f.beginPath(); f.ellipse(u * 2400 + dx, 380 - u * 260 + (a - .5) * 100, 80 + b * 190, 18 + c2 * 32, -.17, 0, 7); f.fill();
    }
  });
  const milkyG = band((b, c2, d) => `rgba(205,205,210,${.025 + d * .035})`);
  const milkyC = band((b, c2, d) => b < .5 ? `rgba(${150 + c2 * 60 | 0},90,255,${.05 + d * .07})` : `rgba(60,${190 + c2 * 50 | 0},230,${.04 + d * .06})`);
  const fog = blurLayer(1800, 260, 60, f => {
    f.fillStyle = `rgba(185,188,195,${.04 + Math.random() * .06})`;
    const fx = Math.random() * 1800, fy = 150 + Math.random() * 80, rx = 120 + Math.random() * 220, ry = 22 + Math.random() * 30;
    for (const dx of [-1800, 0, 1800]) { f.beginPath(); f.ellipse(fx + dx, fy, rx, ry, 0, 0, 7); f.fill(); }
  });
  const layers = [[.08, 300, .5, .5], [.18, 140, .9, .7], [.35, 46, 1.5, .9]].map(([par, n, sz, al]) => ({
    par, al, s: Array.from({ length: n }, () => [Math.random() * 3200, Math.random() * BASE_H * .86, Math.random() * sz + .3, Math.random() * 9, Math.random() < .15, Math.random()])
  }));
  const motes = Array.from({ length: 180 }, () => [Math.random() * GAP * 7.6 - 260, Math.random() - .5, Math.random() * 6.28, Math.random()]);
  const grainC = document.createElement('canvas'); grainC.width = grainC.height = 200;
  const gx = grainC.getContext('2d'), gimg = gx.createImageData(200, 200);
  function grain() { for (let i = 0; i < gimg.data.length; i += 4) { const v = Math.random() * 255; gimg.data[i] = gimg.data[i + 1] = gimg.data[i + 2] = v; gimg.data[i + 3] = 255; } gx.putImageData(gimg, 0, 0); }
  const aur = document.createElement('canvas'), ax = aur.getContext('2d');
  resize(); addEventListener('resize', resize);

  // ---------- replay → timeline ----------
  let R = null, TL = null;
  function buildTimeline(rep) {
    const beats = []; let t = 0;
    const push = (b, d) => { b.t0 = t; b.t1 = t + d; t += d; beats.push(b); };
    push({ k: 'intro' }, 3.4);
    rep.modules.forEach((m, mi) => {
      if (mi > 0) push({ k: 'swoop', mi }, 1.7);
      if ((m.error || '').startsWith('blocked')) { push({ k: 'dwell', mi, at: 0, blocked: true }, 3); return; }
      const hist = m.history && m.history.length ? m.history
        : [{ attempt: 1, passed: m.tests_passed, total: m.tests_total, failures: [], explanation: null }];
      let pos = 0;
      const mv = (to, d = 1.7, back = false) => { push({ k: 'move', mi, a: pos, b: to, back }, d); pos = to; };
      const talk = (at, d) => (window.Captions && Captions.narrates(mi, at) ? Math.max(d, READ) : d);  // time to read the caption
      push({ k: 'dwell', mi, at: 0 }, talk(0, 1.6));
      mv(1); push({ k: 'dwell', mi, at: 1 }, talk(1, 2.6));
      mv(2); push({ k: 'dwell', mi, at: 2 }, talk(2, 2.2));
      mv(3); push({ k: 'dwell', mi, at: 3 }, talk(3, 2.2));
      hist.forEach((h, hi) => {
        if (pos === 5) mv(4, 2.8, true); else mv(4);
        push({ k: 'dwell', mi, at: 4, h: hi }, talk(4, hi ? 2.4 : 2.2));
        mv(5);
        const fail = h.passed < h.total;
        push({ k: 'dwell', mi, at: 5, h: hi, fail }, fail ? 6.4 : talk(5, 2.6));
        if (fail && (m.human_hints || []).some(x => x.attempt === hi + 2)) push({ k: 'dwell', mi, at: 5, h: hi, review: true, sent: true }, REVIEW_DUR);
      });
      if (m.status === 'done') { mv(6); push({ k: 'dwell', mi, at: 6, done: true }, talk(6, 3)); }
      else push({ k: 'dwell', mi, at: 5, failedEnd: true }, 3.6);
    });
    push({ k: 'outro' }, 6);
    return { beats, end: t };
  }
  const READ = 4.2;  // seconds a narrated stop holds
  const REVIEW_DUR = 8.5;  // a person reads the failing case, types the hint, sends it (web/hints.js types it)
  function beatAt(t) {
    const b = TL.beats; let lo = 0, hi = b.length - 1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (b[mid].t1 < t) lo = mid + 1; else hi = mid; }
    return b[lo];
  }

  // ---------- playback ----------
  const skipBtn = document.getElementById('skip-review') || { hidden: true };
  let clock = 0, last = performance.now(), speed = 1, playing = false, chase = false, focus = null, resumeAfter = false, focusX = null;  // focusX: world x the open readout is about
  let cam = 0, cs = 0, trail = [], fr = 0, shoot = null, hits = [];
  let travel = null;  // one presenter click: fly to the next stop, then wait there
  let entrance = null;  // the upload star becomes the first program at Discover
  let SIM = null;  // a dropped codebase replaying its recorded run step by step: { full, n events revealed }
  const playBtn = document.getElementById('play');
  playBtn.onclick = () => {
    if (!R || entrance) return;
    resumeAfter = false;
    if (travel) { travel = null; playing = false; } else playing = !playing;
    syncPlayback();
  };
  const previousBtn = document.getElementById('previous-step'), nextBtn = document.getElementById('next-step');
  const stepStatus = document.getElementById('step-status');
  previousBtn.onclick = () => step(-1);
  nextBtn.onclick = () => step(1);
  document.getElementById('restart').onclick = restart;
  document.getElementById('speed').onchange = e => { speed = +e.target.value; };
  function stops() { return TL ? TL.beats.filter(b => ['dwell', 'outro'].includes(b.k)) : []; }
  function stopTime(b) { return b.t0 + (b.k === 'outro' ? 3 : Math.min(4, b.t1 - b.t0 - .65)); }
  function stopIndex(list) {
    let i = 0;
    while (i + 1 < list.length && clock >= list[i + 1].t0) i++;
    return i;
  }
  function betweenStops(list, i) { return i < list.length - 1 && clock >= list[i].t1; }
  function syncPlayback() {
    const label = playing || travel ? 'Pause' : 'Auto-play';
    if (playBtn.textContent !== label) playBtn.textContent = label;
    playBtn.setAttribute('aria-label', label);
    const list = stops(), i = travel ? travel.index : stopIndex(list), b = list[i];
    playBtn.disabled = !R || !!entrance;
    previousBtn.disabled = !R || !!entrance || !!travel || (i === 0 && !betweenStops(list, i));
    const canFinishStep = !!SIM && !!TL && TL.beats.some(q => q.working);  // a replayed run: Next lands the working step's result
    nextBtn.disabled = !R || !!entrance || !!travel || (i >= list.length - 1 && !canFinishStep);
    const label2 = b ? `${entrance ? 'Arriving → ' : travel ? 'Travelling → ' : ''}${b.k === 'outro' ? 'Summary' : b.review ? 'Needs a person' : STATIONS[b.at][1]} · ${i + 1}/${list.length}` : '';
    if (stepStatus.textContent !== label2) stepStatus.textContent = label2;
    stepStatus.dataset.time = clock.toFixed(3);
    stepStatus.dataset.playing = String(playing);
    stepStatus.dataset.travelling = String(!!travel);
    stepStatus.dataset.entering = String(!!entrance);
  }
  function step(direction) {
    if (!R || !TL || intakeOpen() || travel || entrance) return;
    chase = false;  // the presenter has taken over
    if (SIM && direction > 0) {  // replay: Next skips the wait and lands this step's real result
      const b = beatAt(Math.min(clock, TL.end - 1e-3));
      if (b.working && b.review && !SIM.hintSent) { sendHint(null); return; }  // Next sends the run's own hint
      if (b.working) { SIM.n++; simApply(); clock = Math.max(clock, b.t0); syncPlayback(); return; }
    }
    const list = stops(), current = stopIndex(list), between = betweenStops(list, current);
    const i = Math.max(0, Math.min(list.length - 1, current + (direction < 0 && between ? 0 : direction))), b = list[i];
    if (i === current && !between) return;
    // A clicked readout must not resume playback when an arrow closes it.
    resumeAfter = false; closePanel(); closeCaption(); focus = null; focusX = null; playing = false;
    const target = stopTime(b), forward = target > clock;
    const moves = TL.beats.filter(q => ['move', 'swoop'].includes(q.k) &&
      q.t1 > Math.min(clock, target) && q.t0 < Math.max(clock, target));
    // Skip the old/new station's reading time, but animate the existing path in full.
    // Running that path backwards makes Back retrace the star's route, including retries.
    const from = moves.length ? (forward ? Math.max(clock, moves[0].t0) : Math.min(clock, moves[moves.length - 1].t1 - .001)) : clock;
    const to = moves.length ? (forward ? moves[moves.length - 1].t1 - .001 : moves[0].t0 + .001) : target;
    travel = { from, to, target, index: i, elapsed: 0, duration: moves.length ? 1.6 : .5 };
    clock = from;
    trail = []; lastFail = null;
    syncPlayback();
  }
  function advanceTravel(seconds) {
    if (!travel) return;
    travel.elapsed = Math.min(travel.duration, travel.elapsed + seconds);
    clock = travel.from + (travel.to - travel.from) * travel.elapsed / travel.duration;
    if (travel.elapsed >= travel.duration) { clock = travel.target; travel = null; }
  }
  function restart() {
    cancelEntrance(); chase = false;
    if (SIM) { travel = null; resumeAfter = false; closePanel(); closeCaption(); return startSim(SIM.full); }
    travel = null; resumeAfter = false; closePanel(); closeCaption();
    clock = R && !R.live && stops().length ? stopTime(stops()[0]) : 0; cam = 0; cs = 0; trail = []; lastFail = null;
    playing = !!(R && R.live); syncPlayback();
  }
  function sceneAnchor() { return { x: W > 760 ? W * .36 : W / 2, y: CY }; }
  function cancelEntrance() { finishEntrance(false); }
  function finishEntrance(completed) {
    if (!entrance) return;
    const pending = entrance; entrance = null;
    intake.classList.remove('entering'); intake.inert = false;
    intake.setAttribute('aria-hidden', 'false');
    pending.resolve(completed);
  }
  function startEntrance() {
    cancelEntrance();
    if (reducedMotion.matches) return Promise.resolve(true);
    const rect = drop.querySelector('.drop-ring').getBoundingClientRect();
    return new Promise(resolve => {
      entrance = { elapsed: 0, duration: 1.5,
        fromX: clamp((rect.left + rect.width / 2) / innerWidth, .05, .95),
        fromY: clamp((rect.top + rect.height / 2) / innerHeight, .05, .95), resolve };
      intake.classList.add('entering'); intake.inert = true;
      intake.setAttribute('aria-hidden', 'true');
      syncPlayback();
    });
  }
  function advanceEntrance(seconds) {
    if (!entrance) return null;
    entrance.elapsed = Math.min(entrance.duration, entrance.elapsed + seconds);
    return entrance;
  }
  function entrancePose(entry) {
    const u = clamp(entry.elapsed / entry.duration), reveal = ease(clamp((u - .55) / .45));
    const source = { x: entry.fromX * W, y: entry.fromY * H }, target = sceneAnchor();
    return { u, reveal, source, target,
      x: source.x + (target.x - source.x) * reveal, y: source.y + (target.y - source.y) * reveal,
      zoom: 1 + 7 * ease(clamp(u / .55)),
      power: u < .55 ? .28 + 4.72 * ease(u / .55) : 5 - 4 * reveal,
      shade: u < .55 ? ease(clamp((u - .15) / .4)) : 1 - reveal };
  }
  addEventListener('keydown', e => {
    if (entrance) { if (e.key === 'Escape') { e.preventDefault(); openIntake(); } return; }
    if (['SELECT', 'INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;
    if (intakeOpen()) { if (e.key === 'Escape' && R) closeIntake(); if (e.key === 'Enter' && caseFile.classList.contains('open')) document.getElementById('case-go').click(); return; }
    if (e.code === 'Space') { e.preventDefault(); playBtn.click(); }
    if (e.key === 'r' || e.key === 'R') restart();
    if (e.key === 'Escape') { if (panel.classList.contains('open')) closePanel(); else closeCaption(); }
    if ((e.key === 'Enter' || e.key === 'd' || e.key === 'D') && capFocus !== null) { e.preventDefault(); openStation(capFocus); }
    if (/^[1-7]$/.test(e.key) && R) { const n = +e.key - 1; if (capFocus === n && !panel.classList.contains('open')) openStation(n); else openCaption(n); }
    if (e.key === 'ArrowRight') { e.preventDefault(); if (!e.repeat) step(1); }
    if ((e.key === 'h' || e.key === 'H') && !e.metaKey && !e.ctrlKey && SIM) { e.preventDefault(); skipToReview(); }  // rehearsal: to the human loop
    if (e.key === 'ArrowLeft') { e.preventDefault(); if (!e.repeat) step(-1); }
  });

  // ---------- module text for the scene ----------
  function subtitle(m, i, b, u) {
    if (b.working && b.review) return 'WAITING FOR A PERSON';
    if (b.working) return 'WORKING' + '.'.repeat(1 + Math.floor(performance.now() / 500) % 3);
    const n = R.modules.length;
    const h = b.h !== undefined ? m.history[b.h] : null;
    switch (i) {
      case 0: return b.blocked ? `WAITING ON ${(m.error.match(/dependency (\S+)/) || [])[1] || 'A DEPENDENCY'}`.toUpperCase()
        : `${n} PROGRAM${n > 1 ? 'S' : ''}${m.depends_on.length ? ' · CALLS ' + m.depends_on.join(', ').toUpperCase() : ''}`;
      case 1: return 'NEMOTRON WRITES THE SPEC';
      case 2: return `${m.tests_total || (m.golden || []).length} TEST INPUTS`;
      case 3: return 'REAL COBOL RUN · ANSWER KEY';
      case 4: return h && b.h > 0 ? `ATTEMPT ${h.attempt} · FIXING ${m.history[b.h - 1].total - m.history[b.h - 1].passed} FAILURES` : 'NEMOTRON WRITES PYTHON';
      case 5: {
        if (!h) return 'EVERY OUTPUT MUST MATCH';
        const shown = Math.round(h.passed * clamp(u / .45));
        return `${shown} / ${h.total} MATCH`;
      }
      case 6: return `${m.tests_passed} / ${m.tests_total} · ACCEPTED`;
    }
    return '';
  }

  // ---------- drawing primitives ----------
  function spike(cx, cy, len, ang, w, a, col) {
    x.save(); x.translate(cx, cy); x.rotate(ang);
    const g = x.createLinearGradient(-len, 0, len, 0);
    g.addColorStop(0, `rgba(${col},0)`); g.addColorStop(.5, `rgba(${col},${a})`); g.addColorStop(1, `rgba(${col},0)`);
    x.fillStyle = g; x.fillRect(-len, -w / 2, len * 2, w); x.restore();
  }
  function star(cx, cy, t, power, glow, spk, hitId) {
    const tw = 1 + .12 * Math.sin(t * 7) + .06 * Math.sin(t * 13.1);
    const halo = x.createRadialGradient(cx, cy, 0, cx, cy, 50 * power);
    halo.addColorStop(0, `rgba(${glow},${.4 * power})`); halo.addColorStop(.35, `rgba(${glow},${.12 * power})`); halo.addColorStop(1, `rgba(${glow},0)`);
    x.fillStyle = halo; x.beginPath(); x.arc(cx, cy, 50 * power, 0, 7); x.fill();
    const L = 34 * power * tw, rot = t * .15;
    spike(cx, cy, L, rot, 1.4, .9, spk); spike(cx, cy, L, rot + Math.PI / 2, 1.4, .9, spk);
    spike(cx, cy, L * .45, rot + Math.PI / 4, 1, .5, spk); spike(cx, cy, L * .45, rot - Math.PI / 4, 1, .5, spk);
    const core = x.createRadialGradient(cx, cy, 0, cx, cy, 5 * power);
    core.addColorStop(0, '#fff'); core.addColorStop(.5, `rgba(${spk},.9)`); core.addColorStop(1, `rgba(${glow},0)`);
    x.fillStyle = core; x.beginPath(); x.arc(cx, cy, 5 * power, 0, 7); x.fill();
    if (hitId !== undefined) hits.push({ x: cx, y: cy, r: Math.max(16, 22 * power), id: hitId });
  }
  function drawAurora(t, c, accepted = false) {
    if (c < .02) return;
    const w = aur.width, h = aur.height, sx = w / W, sy = h / H;
    ax.setTransform(1, 0, 0, 1, 0, 0); ax.clearRect(0, 0, w, h); ax.setTransform(sx, 0, 0, sy, 0, 0);
    const curtains = [[0, .55, [120, 255, 200], [150, 90, 255]], [.33, .42, [170, 110, 255], [90, 200, 255]], [.7, .5, [110, 240, 210], [200, 120, 255]]];
    for (const [off, amp, greenTop, greenBottom] of curtains) {
      const top = accepted ? greenTop : [185, 140, 255], bot = accepted ? greenBottom : [90, 200, 255];
      for (let i = 0; i <= W; i += 4) {
        const k = i / W, wave = Math.sin(k * 6 + t * .6 + off * 9) * 32 + Math.sin(k * 13 - t * .9 + off * 4) * 12;
        const y0 = 34 + off * 46 + wave, hh = 120 + 80 * Math.sin(k * 4 + t * .4 + off * 7) ** 2, f = .5 + .5 * Math.sin(k * 9 + t * 1.2 + off * 5);
        const g = ax.createLinearGradient(0, y0, 0, y0 + hh), tc = rgb(mix(top, bot, f));
        g.addColorStop(0, `rgba(${tc},0)`); g.addColorStop(.25, `rgba(${tc},${.11 * c * amp})`); g.addColorStop(1, `rgba(${rgb(bot)},0)`);
        ax.fillStyle = g; ax.fillRect(i, y0, 4, hh);
      }
    }
    x.save(); x.globalCompositeOperation = 'lighter'; x.drawImage(aur, 0, 0, W, H); x.restore();
  }
  const pathY = (wx, t) => CY + Math.sin(wx * .006 + t * .35) * 2.2 + Math.sin(wx * .017 - t * .5) * 1.2;
  function filament(ox, t, c, starX, lc) {
    const g = x.createLinearGradient(0, 0, W, 0), s = clamp(starX / W, .02, .98);
    g.addColorStop(0, `rgba(${lc},0)`); g.addColorStop(Math.max(.01, s - .3), `rgba(${lc},${.1 + .08 * c})`);
    g.addColorStop(s, `rgba(${lc},${.22 + .12 * c})`); g.addColorStop(Math.min(.99, s + .25), `rgba(${lc},.05)`); g.addColorStop(1, `rgba(${lc},0)`);
    x.save(); x.globalCompositeOperation = 'lighter'; x.strokeStyle = g;
    for (const [lw, al] of [[9, .1], [3, .25], [.7, .9]]) {
      x.lineWidth = lw; x.globalAlpha = al; x.beginPath();
      for (let i = -10; i <= W + 10; i += 6) { const y = pathY(i - ox, t); i <= -10 ? x.moveTo(i, y) : x.lineTo(i, y); }
      x.stroke();
    }
    x.globalAlpha = 1;
    for (const m of motes) {
      const px = m[0] + ox; if (px < -10 || px > W + 10) continue;
      const fade = Math.max(0, 1 - Math.abs(px - starX) / (W * .55));
      x.fillStyle = `rgba(${lc},${(.15 + .35 * m[3]) * fade})`; x.fillRect(px, pathY(m[0], t) + m[1] * 14 + Math.sin(t * .8 + m[2]) * 3, 1, 1);
    }
    x.restore();
  }

  // the difference between expected and actual, with a little context either side
  function diffParts(a, b) {
    a = String(a); b = String(b); let i = 0;
    while (i < a.length && i < b.length && a[i] === b[i]) i++;
    let j = 0; while (j < a.length - i && j < b.length - i && a[a.length - 1 - j] === b[b.length - 1 - j]) j++;
    const s = Math.max(0, i - 14), cut = (str) => {
      const e = str.length - j, end = Math.min(str.length, e + 8);
      return [(s > 0 ? '…' : '') + str.slice(s, i), str.slice(i, e) || ' ', str.slice(e, end) + (end < str.length ? '…' : '')];
    };
    return [cut(a), cut(b)];
  }
  function diffLine(parts, cx, y, label, accent, glitch) {
    const [pre, mid, post] = parts, sz = 22;
    const wp = measure(pre, sz, 1, '300'), wm = measure(mid, sz, 1, '300'), wq = measure(post, sz, 1, '300');
    let px = cx - (wp + wm + wq) / 2;
    txt(label, px - 18, y - 4, 9, .45, 3, 'right', accent ? '255,205,220' : '232,234,242');
    txt(pre, px, y, sz, .5, 1, 'left', '225,228,240', '300'); px += wp;
    if (glitch) {
      const fl = Math.random() < .12 ? (Math.random() - .5) * 3 : 0;
      x.save(); x.globalCompositeOperation = 'lighter';
      txt(mid, px + fl + 1.2, y, sz, .45, 1, 'left', '120,220,255', '300'); txt(mid, px + fl - 1.2, y, sz, .55, 1, 'left', '255,120,170', '300');
      x.restore(); txt(mid, px + fl, y, sz, .9, 1, 'left', '255,215,230', '300');
    } else txt(mid, px, y, sz, .98, 1, 'left', '245,246,252', '300');
    txt(post, px + wm, y, sz, .5, 1, 'left', '225,228,240', '300');
  }


  // ---------- narration: one sentence and one proof next to the ring ----------
  const SANS = '-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif';
  let capFocus = null;
  function sans(s, px, py, sz, a, col = '242,241,248', wt = '400') {
    x.font = `${wt} ${sz}px ${SANS}`; x.fillStyle = `rgba(${col},${a})`; x.textAlign = 'left'; setLS(0); x.fillText(s, px, py);
  }
  function wrapSans(s, max, sz) {
    const go = m => { x.font = `400 ${sz}px ${SANS}`; const out = []; let cur = '';
      for (const w of String(s).split(/\s+/)) { const tr = cur ? cur + ' ' + w : w; if (x.measureText(tr).width > m && cur) { out.push(cur); cur = w; } else cur = tr; }
      if (cur) out.push(cur); return out; };
    let out = go(max);
    // no lonely last word: narrow the measure until the last line carries at least two
    for (let m = max * .92; out.length > 1 && !/\s/.test(out[out.length - 1]) && m > max * .55; m *= .92) out = go(m);
    return out;
  }
  function moduleNow() {
    const b = beatAt(Math.min(clock, TL.end - 1e-3));
    return b.mi !== undefined ? b.mi : (b.k === 'outro' ? R.modules.length - 1 : 0);
  }
  function openCaption(i) {
    closePanel(); hold(i * GAP); capFocus = i; focus = i;
  }
  function closeCaption() {
    if (capFocus === null) return;
    capFocus = null; focus = null; focusX = null;
    if (resumeAfter) { playing = true; playBtn.textContent = 'Pause'; }
  }
  // which caption is up right now: a clicked ring, or the stop the star is sitting at
  function activeCaption(t, b, u) {
    if (!window.Captions) return null;
    if (capFocus !== null) {
      const mi = moduleNow(), m = R.modules[mi], hist = m.history || [];
      const ai = capFocus === 5 ? Math.max(0, hist.findIndex(a => a.passed < a.total)) : Math.max(0, hist.length - 1);
      return { n: capFocus, mi, a: 1, since: 0, ai, clicked: true };
    }
    if (b.k === 'dwell' && b.review) return null;  // a person is being asked: the Needs-a-person panel has the floor
    if (b.k === 'dwell' && b.working) return { n: b.at, mi: b.mi, a: clamp((t - b.t0 - .35) / .55), since: b.t0 + .35, ai: b.h || 0, working: true, beat: b, t };
    let nb = b, tail = 1;
    if (b.k === 'move' && b.back && lastFail) { nb = lastFail; tail = clamp(1 - (t - b.t0) / 1.1); }  // the reason lingers as the star goes back
    if (nb.k !== 'dwell' || nb.blocked || !Captions.narrates(nb.mi, nb.at)) return null;
    const dt = t - nb.t0, dur = nb.t1 - nb.t0;
    const a = clamp((dt - .35) / .55) * (nb === b ? clamp((dur - dt) / .6) : tail) * (nb.fail && nb === b ? 1 : 1);
    return { n: nb.at, mi: nb.mi, a, since: nb.t0 + .35, ai: nb.h !== undefined ? nb.h : (R.modules[nb.mi].history || []).length - 1, dt };
  }
  // what a live run is doing right now, with how long this step has taken so far
  const workSince = new Map();
  function workingCaption(ac, m) {
    const key = `${R.name}|${ac.mi}|${ac.n}|${ac.ai}`;
    if (!workSince.has(key)) workSince.set(key, performance.now());
    const real = R.sim && ac.beat && ac.beat.workDur  // replay: real seconds this step had taken by now
      ? Math.min(ac.beat.realGap, (ac.t - ac.beat.t0) * ac.beat.realGap / ac.beat.workDur) : (performance.now() - workSince.get(key)) / 1000;
    const s = Math.floor(real), clock = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
    const say = {
      0: 'Mapping the codebase: which programs call which.',
      1: 'Nemotron is reading the COBOL and writing down what it does.',
      2: 'Nemotron is inventing test inputs. Then the real COBOL records the answers.',
      4: ac.ai > 0 ? 'Nemotron is fixing the Python, using the cases it got wrong.' : 'Nemotron is writing the Python.',
      5: 'Running every test against the original COBOL.',
      6: 'Writing unit tests for the verified Python.',
    }[ac.n] || 'Working.';
    return { sentence: say, proof: { kind: 'line', text: `${R.sim ? 'REAL RUN' : 'LIVE'}   ·   ${clock}` } };
  }
  function narration(t, ox, lc, b, u) {
    const ac = activeCaption(t, b, u);
    if (!ac || ac.a < .01) return;
    const m = R.modules[ac.mi], hist = m.history || [], attempt = hist[ac.ai] || null;
    const cp = ac.working ? workingCaption(ac, m) : Captions.get(ac.n + 1, { module: m, replay: R, attempt, attemptIndex: ac.ai, mutation: R.kind === 'mutation' });
    if (!cp) return;
    const key = `${ac.n}|${ac.mi}|${ac.ai}`;
    if (ac.clicked && narration.lastKey !== key) { narration.lastKey = key; narration.clickT = performance.now() / 1000; }
    if (!ac.clicked) narration.lastKey = null;
    // auto captions are timed from their stop, so scrubbing and replays look identical; clicked ones run on real time
    const age = ac.clicked ? performance.now() / 1000 - narration.clickT : t - ac.since;
    const sx = ac.n * GAP + ox, A = ac.a;
    const right = W - (sx + 96) >= 300, compact = !right;  // narrow screens: a smaller caption above the ring
    const x0 = right ? sx + 96 : 28, maxW = right ? Math.min(440, W - x0 - 32) : W - 56;
    const y0 = right ? CY - 152 : 76;
    const S1 = compact ? 15.5 : 17, S2 = compact ? 13.5 : 14.5, DZ = compact ? 17 : 20;

    // a soft darkening behind the words, no box: legible over the aurora
    const veil = x.createRadialGradient(x0 + maxW * .4, y0 + 70, 10, x0 + maxW * .4, y0 + 70, maxW * .75);
    veil.addColorStop(0, `rgba(5,4,12,${.5 * A})`); veil.addColorStop(1, 'rgba(5,4,12,0)');
    x.fillStyle = veil; x.fillRect(x0 - maxW * .4, y0 - 60, maxW * 1.7, 260);

    // leader line from the ring to the caption, drawn on as it appears
    const lead = clamp(age / .5);
    x.save(); x.strokeStyle = `rgba(${lc},${.42 * A})`; x.lineWidth = .7; x.beginPath();
    if (compact) { const top = CY - 30, end = CY - 30 - 18 * ease(lead); x.moveTo(sx, top); x.lineTo(sx, end); }  // a short stem up toward the caption
    else {
      const ex = sx + 17, ey = CY - 17, kx = x0 - 26, ky = y0 - 4; x.moveTo(ex, ey);
      const l1 = Math.hypot(kx - ex, ky - ey), tot = l1 + 16, d = tot * ease(lead);
      if (d <= l1) x.lineTo(ex + (kx - ex) * d / l1, ey + (ky - ey) * d / l1); else { x.lineTo(kx, ky); x.lineTo(kx + (d - l1), ky); }
    }
    x.stroke(); x.restore();

    const st = STATIONS[ac.n], fileTag = (m.file || m.id).toUpperCase();
    let y = y0;
    const step = k => clamp((age - .25 - k * .12) / .45) * A;  // each line drifts in after the one above
    txt(`${st[0]} — ${st[1].toUpperCase()}  ·  ${fileTag}`, x0, y, 9.5, .5 * step(0), 3, 'left');
    y += compact ? 24 : 30;
    for (const ln of wrapSans(cp.sentence, maxW, S1)) { sans(ln, x0, y, S1, .96 * step(1)); y += S1 + 6; }
    if (cp.sub && !(compact && cp.proof && cp.proof.kind === 'diff')) { y += 1; for (const ln of wrapSans(cp.sub, maxW, S2)) { sans(ln, x0, y, S2, .66 * step(2)); y += S2 + 5; } }
    y += compact ? 10 : 16;
    const pr = cp.proof, pa = step(3);
    if (pr && pr.kind === 'line') { wrap(pr.text, maxW, 12.5, 1.5).slice(0, 2).forEach(ln => { txt(ln, x0, y, 12.5, .82 * pa, 1.5, 'left', '236,232,252'); y += 20; }); y += 4; }
    if (pr && pr.kind === 'pair') {
      txt(pr.left, x0, y, 12.5, .55 * pa, 1, 'left'); const wl = measure(pr.left, 12.5, 1);
      txt('→', x0 + wl + 14, y, 12.5, .45 * pa, 0, 'left', lc); txt(pr.right, x0 + wl + 36, y, 12.5, .9 * pa, 1, 'left', '242,241,248'); y += 24;
    }
    if (pr && pr.kind === 'diff') {
      if (!compact) { txt(`INPUT  ${pr.input}`, x0, y, 9.5, .45 * pa, 2.5, 'left'); y += 26; } else y += 8;
      const [da, db] = diffParts(pr.expected, pr.actual), row = (parts, label, bad) => {
        txt(label, x0, y - 4, 9, .42 * pa, 3, 'left', bad ? '255,205,220' : '232,234,242');
        let px = x0 + 82; const [pre, mid, post] = parts, sz = DZ;
        txt(pre, px, y, sz, .5 * pa, 1, 'left', '225,228,240', '300'); px += measure(pre, sz, 1, '300');
        if (bad) {
          const fl = Math.random() < .1 ? (Math.random() - .5) * 2.5 : 0;
          x.save(); x.globalCompositeOperation = 'lighter';
          txt(mid, px + fl + 1.1, y, sz, .4 * pa, 1, 'left', '120,220,255', '300'); txt(mid, px + fl - 1.1, y, sz, .5 * pa, 1, 'left', '255,120,170', '300');
          x.restore(); txt(mid, px + fl, y, sz, .92 * pa, 1, 'left', '255,215,230', '300');
        } else txt(mid, px, y, sz, pa, 1, 'left', '248,247,252', '300');
        txt(post, px + measure(mid, sz, 1, '300'), y, sz, .5 * pa, 1, 'left', '225,228,240', '300');
        y += compact ? 24 : 28;
      };
      row(da, 'COBOL', false); row(db, 'REWRITE', true);
    }
    if (cp.note && !compact) {  // narrow screens keep the reason for DETAILS
      const na = step(4), n = Math.max(0, Math.floor((age - .9) * 60)), lines = wrapSans(cp.note, maxW, 13.5).slice(0, 2);
      let left = n; y += 6;
      x.font = `italic 400 13.5px ${SANS}`;
      lines.forEach(ln => { if (left <= 0) return; const s2 = ln.slice(0, left); left -= ln.length + 1;
        x.font = `italic 400 13.5px ${SANS}`; x.fillStyle = `rgba(236,232,252,${.72 * na})`; x.textAlign = 'left'; x.fillText(s2, x0, y); y += 19; });
      txt('NEMOTRON', x0, y + 2, 9, .5 * na, 3, 'left', '212,196,255'); y += 18;
    }
    // DETAILS: the full station readout (code, answer key, attempts)
    y += 12;
    const da2 = step(5) * (ac.clicked ? .85 : .5);
    txt('DETAILS  →', x0, y, 9.5, da2, 3, 'left', '212,196,255');
    hits.push({ x: x0 + 46, y: y - 4, r: 26, id: 'det:' + ac.n });
  }

  // ---------- star-chart leader: ties the open readout to its ring or star ----------
  let leadIn = 0;
  function leader(t, ox, lc) {
    const open = panel.classList.contains('open');
    leadIn = open ? Math.min(1, leadIn + .045) : 0; if (!open) return;
    let ax, ay, r;
    if (focus !== null) { ax = focus * GAP + ox; ay = CY; r = 34; }
    else if (pStar !== null) { const hh = hits.find(q => q.id === pStar); if (!hh) return; ax = hh.x; ay = hh.y; r = 14; }
    else return;
    const px = (innerWidth - panel.offsetWidth) / K + 58 / K, py = 62 / K + 4;
    if (px <= ax + r + 20) return;
    const ex = ax + r * .72, ey = ay - r * .72, kx = ex + Math.max(18, Math.min(60, (py < ey ? ey - py : 30))), ky = py;
    const seg = [[ex, ey], [kx, ky], [px, py]], len = Math.hypot(kx - ex, ky - ey) + (px - kx), draw = len * ease(leadIn);
    x.save(); x.strokeStyle = `rgba(${lc},.42)`; x.lineWidth = .7; x.beginPath(); x.moveTo(ex, ey);
    const l1 = Math.hypot(kx - ex, ky - ey);
    if (draw <= l1) { const f = draw / l1; x.lineTo(ex + (kx - ex) * f, ey + (ky - ey) * f); }
    else { x.lineTo(kx, ky); x.lineTo(kx + (draw - l1), ky); }
    x.stroke();
    x.strokeStyle = `rgba(${lc},.55)`; x.beginPath(); x.arc(ax, ay, r + 5, -Math.PI * .42, -Math.PI * .08); x.stroke();
    if (leadIn >= 1) { x.fillStyle = `rgba(${lc},.7)`; x.fillRect(px - 1, py - 1, 2, 2); }
    x.restore();
  }

  // ---------- the frame ----------
  let lastFail = null;
  const CLUSTER = [[-74, -92], [-164, -118], [-36, -150], [-214, -58], [-128, -44], [-250, -150]];  // left of Discover: the caption owns the right
  const CONST = [[-150, -112], [-56, -156], [-250, -150], [-96, -58], [-206, -48], [-330, -96]];  // left of Verified, clear of the caption

  function frame(now) {
    const dtReal = Math.min(.05, (now - last) / 1000); last = now;
    requestAnimationFrame(frame);  // first, so one bad frame can never stop the show
    if (!W || !isFinite(W)) { if (!resize()) return; }
    if (cv.width !== Math.round(innerWidth * DPR) || cv.height !== Math.round(innerHeight * DPR)) resize();
    if (entrance) {
      const entry = advanceEntrance(dtReal);
      try {
        x.setTransform(DPR * K, 0, 0, DPR * K, 0, 0); x.globalAlpha = 1;
        x.save(); drawEntrance(entry, now / 1000);
        if (entry.elapsed >= entry.duration) finishEntrance(true);
      } catch (err) {
        cancelEntrance(); note('The transition could not finish. Please try your zip again.', true); console.error(err);
      } finally { x.restore(); }
      syncPlayback(); return;
    }
    if (intakeOpen()) { syncPlayback(); try { x.setTransform(DPR * K, 0, 0, DPR * K, 0, 0); x.globalAlpha = 1; drawSky(now / 1000); } catch (err) { console.error(err); } return; }
    // a live run keeps pace with the real one: when the screen is behind what Nemotron has already
    // done, it plays faster until it is caught up (also to the end, once the run has finished)
    const edge = R && R.live && TL && TL.beats.find(q => q.working);
    if (chase && R && R.finished && clock >= TL.end - .5) chase = false;
    const behind = R && R.live && TL && (chase || edge) ? (edge ? edge.t0 : TL.end) - clock : 0;
    const catchUp = behind > 6 ? Math.max(speed, 2.4) : behind > 2.5 ? Math.max(speed, 1.6) : speed;
    if (travel) advanceTravel(dtReal);
    else if (R && playing) { clock = Math.min(TL.end + 2, clock + dtReal * catchUp); if (SIM) simTick(); }
    syncPlayback();
    if (R) { try { x.setTransform(DPR * K, 0, 0, DPR * K, 0, 0); x.globalAlpha = 1; x.save(); draw(clock); } catch (err) { if (!frame.warned) { frame.warned = true; console.error(err); } } finally { x.restore(); } }
  }

  function drawEntrance(entry, t) {
    const pose = entrancePose(entry);
    if (pose.u < .55) {
      x.save();
      try {
        x.translate(pose.source.x, pose.source.y); x.scale(pose.zoom, pose.zoom);
        x.translate(-pose.source.x, -pose.source.y); drawSky(t);
      } finally { x.restore(); }
    } else {
      cam = W / 2 - pose.target.x; cs = 0;
      draw(clock);
    }
    x.fillStyle = `rgba(7,7,10,${pose.shade})`; x.fillRect(0, 0, W, H);
    star(pose.x, pose.y, clock, pose.power,
      rgb(mix([232,234,242], [215,225,255], pose.reveal)),
      rgb(mix([242,241,248], [240,244,255], pose.reveal)));
  }

  // ---------- the sky alone, behind the intake ----------
  function drawSky(t) {
    fr++; const ox = -t * 6;
    x.fillStyle = '#07070a'; x.fillRect(0, 0, W, H);
    const mo = ((ox * .12) % 2400 + 2400) % 2400; x.drawImage(milkyG, mo - 2400, 0); x.drawImage(milkyG, mo, 0);
    for (const L of layers) for (const d of L.s) {
      const px = ((d[0] + ox * L.par) % (W + 60) + W + 60) % (W + 60) - 30;
      x.fillStyle = `rgba(232,236,250,${L.al * (.35 + .35 * Math.sin(t * (d[4] ? 3.5 : 1.2) + d[3]))})`; x.fillRect(px, d[1], d[2], d[2]);
    }
    if (intake.classList.contains('open') && !entrance) drawIntakeComet(t);
    const fo = ((ox * .55) % 1800 + 1800) % 1800; x.globalAlpha = .75; x.drawImage(fog, fo - 1800, H - 190); x.drawImage(fog, fo, H - 190); x.globalAlpha = 1;
    if (fr % 3 === 0) grain(); x.globalAlpha = .06; x.fillStyle = x.createPattern(grainC, 'repeat'); x.fillRect(0, 0, W, H); x.globalAlpha = 1;
    const vg = x.createRadialGradient(W / 2, H / 2, H * .2, W / 2, H / 2, W * .75); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,.8)');
    x.fillStyle = vg; x.fillRect(0, 0, W, H);
  }

  function drawIntakeComet(t) {
    if (reducedMotion.matches) return;
    const u = (t % 6) / 2.2;
    if (u >= 1) return;
    const px = -180 + u * (W + 360), py = H * .25 + u * 32;
    const gradient = x.createLinearGradient(px - 150, py - 8, px, py);
    gradient.addColorStop(0, 'rgba(232,236,250,0)');
    gradient.addColorStop(1, 'rgba(232,236,250,.65)');
    x.strokeStyle = gradient; x.lineWidth = .8;
    x.beginPath(); x.moveTo(px - 150, py - 8); x.lineTo(px, py); x.stroke();
    star(px, py, t, .28, '215,222,240', '235,238,248');
  }

  // ---------- live: the timeline so far, ending in a "working" stop where the run is now ----------
  // Same beats and durations as buildTimeline for every finished step, so when a step completes
  // its working stop is replaced in place and the replay simply carries on.
  function liveTimeline(rep) {
    const beats = []; let t = 0;
    const push = (b, d) => { b.t0 = t; b.t1 = t + d; t += d; beats.push(b); };
    const work = b => { b.working = true; push(b, 1e5); };
    push({ k: 'intro' }, 3.4);
    for (let mi = 0; mi < rep.modules.length; mi++) {
      const m = rep.modules[mi], evs = (rep.events || []).filter(e => e.module === m.id), has = n => evs.some(e => e.node === n);
      const failed = m.status === 'failed', talk = (at, d) => (window.Captions && Captions.narrates(mi, at) ? Math.max(d, READ) : d);
      if (mi > 0) push({ k: 'swoop', mi }, 1.7);
      if ((m.error || '').startsWith('blocked')) { push({ k: 'dwell', mi, at: 0, blocked: true }, 3); continue; }
      if (!evs.length) {  // Discover needs no model: the program is mapped, and Nemotron starts reading it
        push({ k: 'dwell', mi, at: 0 }, talk(0, 1.6)); push({ k: 'move', mi, a: 0, b: 1 }, 1.7); work({ k: 'dwell', mi, at: 1 }); break;
      }
      let pos = 0; const mv = (to, d = 1.7, back = false) => { push({ k: 'move', mi, a: pos, b: to, back }, d); pos = to; };
      const end = at => (failed ? (push({ k: 'dwell', mi, at, failedEnd: true }, 3.6), false) : (work({ k: 'dwell', mi, at }), true));
      push({ k: 'dwell', mi, at: 0 }, talk(0, 1.6));
      mv(1); if (!has('extract_spec')) { if (end(1)) break; continue; }
      push({ k: 'dwell', mi, at: 1 }, talk(1, 2.6));
      mv(2); if (!has('record')) { if (end(2)) break; continue; }
      push({ k: 'dwell', mi, at: 2 }, talk(2, 2.2)); mv(3); push({ k: 'dwell', mi, at: 3 }, talk(3, 2.2));
      const rewrites = evs.filter(e => e.node === 'rewrite' && !/^blocked/.test(e.msg || '')).length;
      const verifies = evs.filter(e => e.node === 'verify').length, hist = m.history || [];
      let stop = false, over = false;  // stop: the run is busy here; over: this module ended without passing
      for (let k = 0; k < 10; k++) {
        if (pos === 5) mv(4, 2.8, true); else mv(4);
        if (rewrites <= k) { stop = end(4); over = !stop; break; }
        push({ k: 'dwell', mi, at: 4, h: k }, talk(4, k ? 2.4 : 2.2));
        mv(5);
        if (verifies <= k) { stop = end(5); over = !stop; break; }
        const h = hist[k] || {}, fail = h.total ? h.passed < h.total : false;
        push({ k: 'dwell', mi, at: 5, h: k, fail }, fail ? 6.4 : talk(5, 2.6));
        if (!fail) break;
        // out of attempts: the module asks a person (pipeline needs_review), and the star waits at Verify
        const vIdx = evs.filter(e => e.node === 'verify')[k], after = vIdx ? evs.slice(evs.indexOf(vIdx) + 1) : [];
        const upTo = after.findIndex(e => e.node === 'rewrite'), seg = upTo < 0 ? after : after.slice(0, upTo);
        const asked = seg.some(e => e.node === 'needs_review' && /^could not verify/.test(e.msg || ''));
        const answered = seg.some(e => e.node === 'needs_review' && /^feedback received/.test(e.msg || ''));
        const next = rep.next;  // a replay knows its next real event: the ask is coming
        if (!asked && !seg.length && next && next.module === m.id && next.node === 'needs_review') { work({ k: 'dwell', mi, at: 5, h: k, asking: true }); stop = true; break; }
        if (asked && !answered) { work({ k: 'dwell', mi, at: 5, h: k, review: true }); stop = true; break; }
        if (answered) push({ k: 'dwell', mi, at: 5, h: k, review: true, sent: true }, REVIEW_DUR);
      }
      if (stop) break;
      if (over) continue;
      if (has('accept')) { mv(6); push({ k: 'dwell', mi, at: 6, done: true }, talk(6, 3)); continue; }
      if (failed) { push({ k: 'dwell', mi, at: 5, failedEnd: true }, 3.6); continue; }
      mv(6); work({ k: 'dwell', mi, at: 6 }); break;
    }
    return { beats, end: t };
  }

  // ---------- a recorded real run, replayed the way it happened ----------
  // The recording's events are revealed one at a time into the live engine, so the star waits
  // at a station while that step "works", then the real result lands and it moves on. Each
  // wait is the real step's duration, compressed; the caption shows the real elapsed time.
  const SIM_SPEED = 12;  // real seconds per replayed second while a step works
  const evTime = e => Date.parse(e && e.t) / 1000;
  function simPartial() {
    const full = SIM.full, evs = full.events.slice(0, SIM.n), seen = new Map(), total = new Map();
    evs.forEach(e => seen.set(e.module, (seen.get(e.module) || 0) + 1));
    full.events.forEach(e => total.set(e.module, (total.get(e.module) || 0) + 1));
    const modules = full.modules.map(m => {
      const n = seen.get(m.id) || 0;
      if (n && n >= (total.get(m.id) || 0)) return m;  // finished: the whole record
      // still running: only what the run had produced by now, so Details never shows the future
      const mine = evs.filter(e => e.module === m.id), has = node => mine.some(e => e.node === node);
      const rewrites = mine.filter(e => e.node === 'rewrite' && !/^blocked/.test(e.msg || '')).length;
      const hist = (m.history || []).slice(0, mine.filter(e => e.node === 'verify').length), last = hist[hist.length - 1];
      const src = (m.attempt_sources || []).slice(0, rewrites), golden = has('record') ? m.golden || [] : [];
      const reviews = mine.filter(e => e.node === 'needs_review'), lastEv = mine[mine.length - 1];
      const asking = lastEv && lastEv.node === 'needs_review' && /^could not verify/.test(lastEv.msg || '');
      const answered = reviews.filter(e => /^feedback received/.test(e.msg || '')).length;
      return { ...m, status: asking ? 'needs_review' : n ? 'running' : 'pending', error: null,
               human_hints: (m.human_hints || []).slice(0, answered), spec: has('extract_spec') ? m.spec : null, golden,
               python: rewrites ? (src.length ? src[src.length - 1].python : m.python) : '', attempt_sources: src,
               history: hist, attempts: rewrites, tests_passed: last ? last.passed : 0, tests_total: last ? last.total : golden.length,
               heldout: null, divergences: [], unit_tests_status: null, unit_tests_quarantined: [] };
    });
    const finished = SIM.n >= SIM.end;  // once ended, the programs it never reached leave the sky
    return { ...full, events: evs, modules: finished ? modules.filter(m => seen.has(m.id)) : modules,
             live: false, sim: true, finished, next: full.events[SIM.n] };
  }
  function simApply() {
    const rep = simPartial(), prevWork = TL && TL.beats.find(b => b.working);
    R = rep; TL = rep.finished ? buildTimeline(rep) : liveTimeline(rep);
    if (prevWork && prevWork.review) {  // the hint was sent: carry on from the end of the ask, the star goes back
      const rb = TL.beats.find(q => q.review && q.mi === prevWork.mi && q.h === prevWork.h);
      if (rb && !rb.working) clock = Math.max(clock, rb.t1 - .05);
    }
    if (prevWork && clock > prevWork.t0 && !prevWork.review) {  // the step finished: show its result from the star's arrival
      const nb = beatAt(prevWork.t0 + .01);
      if (!nb.working || nb.mi !== prevWork.mi || nb.at !== prevWork.at || nb.h !== prevWork.h) clock = prevWork.t0;
    }
    if (panel.classList.contains('open')) refreshPanel();
    const w = TL.beats.find(b => b.working);
    if (w) {
      const ev = SIM.full.events, gap = SIM.n ? evTime(ev[SIM.n]) - evTime(ev[SIM.n - 1]) : 10;
      w.realGap = Math.max(1, isFinite(gap) ? gap : 6);
      w.workDur = w.review ? REVIEW_DUR : clamp(w.realGap / SIM_SPEED, 1.4, 3.6);
    }
  }
  function simTick() {  // each frame while playing: finish the working step once its time is up
    if (!SIM || !TL) return;
    if (!skipBtn.hidden && SIM.n > reviewEvent(SIM.full)) skipBtn.hidden = true;
    const w = TL.beats.find(b => b.working);
    if (w && w.review) {  // a person is being asked: wait for the presenter's hint, then a beat to read "sent"
      if (SIM.hintSent && clock >= SIM.sentAt + 2.2) { SIM.n++; simApply(); }
      return;
    }
    if (w && clock >= w.t0 + w.workDur) { SIM.n++; simApply(); }
  }
  // the presenter's hint at the "Needs a person" stop (web/hints.js); null sends the run's recorded hint
  function sendHint(text) {
    if (!SIM || SIM.hintSent) return;
    SIM.hintSent = true; SIM.typedHint = text; SIM.sentAt = clock;
    playing = true; syncPlayback();
  }
  function reviewEvent(full) {  // the first check of a program that later asked a person, in the recording
    const m = (full.modules || []).find(q => (q.human_hints || []).length);
    return m ? full.events.findIndex(e => e.module === m.id && e.node === 'verify') : -1;
  }
  function skipToReview() {
    const i = SIM ? reviewEvent(SIM.full) : -1;
    if (i < 0) return;
    travel = null; resumeAfter = false; closePanel(); closeCaption();
    SIM.n = i; SIM.hintSent = false; simApply();
    const w = TL.beats.find(b => b.working);
    if (w) clock = Math.max(0, w.t0 - 1.7);  // arrive at Verify as its result lands
    cam = 0; cs = 0; trail = []; lastFail = null; playing = true; syncPlayback();
  }
  // a recording with a person's hint is the demo's story: it ends once that program is verified
  function simEnd(full) {
    const m = (full.modules || []).find(q => (q.human_hints || []).length);
    if (!m) return full.events.length;
    return full.events.reduce((end, e, i) => (e.module === m.id ? i + 1 : end), 0);
  }
  function startSim(full, file = SIM && SIM.file) {  // file: the dropped zip's name, for the download
    SIM = { full, n: 0, end: simEnd(full), file }; workSince.clear(); TL = null; simApply();
    skipBtn.hidden = reviewEvent(full) < 0;
    clock = 3.4; cam = 0; cs = 0; trail = []; lastFail = null;  // past the title: the entrance already set the scene
    playing = true; syncPlayback();
  }

  function draw(t) {
    fr++; hits = [];
    const b = beatAt(Math.min(t, TL.end - 1e-3)), mods = R.modules, n = mods.length;
    const mi = b.mi !== undefined ? b.mi : (b.k === 'outro' ? n - 1 : 0), m = mods[mi];
    let p = 0, arc = 0, moving = false, u = 0;
    if (b.k === 'move') { const e = ease(clamp((t - b.t0) / (b.t1 - b.t0))); p = b.a + (b.b - b.a) * e; arc = b.back ? Math.sin(e * Math.PI) : 0; moving = true; }
    else if (b.k === 'dwell') { p = b.at; u = clamp((t - b.t0) / (b.t1 - b.t0)); }
    else if (b.k === 'swoop') { p = 6 - 6 * ease(clamp((t - b.t0) / (b.t1 - b.t0))); }
    else if (b.k === 'outro') p = 6;
    if (b.k === 'dwell' && b.fail) lastFail = b;
    if (lastFail && t < lastFail.t0) lastFail = null;

    const done = i => i < mi ? mods[i].status === 'done' : i === mi && b.k !== 'swoop' && p > 5.98 && m.status === 'done';
    const allDone = mods.every(q => q.status === 'done');
    let target = b.k === 'outro' ? (allDone ? 1 : .5) : b.k === 'swoop' || b.k === 'intro' ? 0 : clamp((p - 3.4) / 2.6);
    cs += (target - cs) * .03; const c = cs;
    const failing = b.k === 'dwell' && b.fail && u > .42;
    const jit = failing && u < .5 && Math.random() < .3 ? (Math.random() - .5) * 7 : 0;
    // an open readout pulls what it describes into the middle of the free sky left of it
    const starAt = sceneAnchor().x;  // left of centre leaves the right side for the caption
    const freeMid = panel.classList.contains('open') ? (innerWidth - panel.getBoundingClientRect().width) / 2 / K : starAt;
    const wx = p * GAP, camT = focusX !== null ? focusX + W / 2 - freeMid : wx + W / 2 - starAt;
    cam += (camT - cam) * (focusX !== null ? .08 : b.k === 'swoop' ? .12 : .055);
    const ox = W / 2 - cam, lc = rgb(mix([225, 230, 245], [195, 170, 255], c));
    const caption = !panel.classList.contains('open') && activeCaption(t, b, u);
    // Above-ring captions get clear space instead of a second cluster behind their words.
    const quietCaption = caption && caption.a > .01 && W - (caption.n * GAP + ox + 96) < 300;

    x.save(); x.translate(jit, 0);
    x.fillStyle = `rgb(${rgb(mix([7, 7, 10], [10, 6, 22], c))})`; x.fillRect(-10, 0, W + 20, H);
    const mo = ((ox * .12) % 2400 + 2400) % 2400;
    x.globalAlpha = 1 - c; x.drawImage(milkyG, mo - 2400, 0); x.drawImage(milkyG, mo, 0);
    x.globalAlpha = c; x.drawImage(milkyC, mo - 2400, 0); x.drawImage(milkyC, mo, 0); x.globalAlpha = 1;
    drawAurora(t, c, b.k === 'outro' ? allDone : p > 5.98 && m.status === 'done');
    for (const L of layers) for (const d of L.s) {
      const px = ((d[0] + ox * L.par) % (W + 60) + W + 60) % (W + 60) - 30;
      const a = L.al * (.35 + .35 * Math.sin(t * (d[4] ? 3.5 : 1.2) + d[3])), sc = rgb(mix([232, 236, 250], d[5] < .5 ? [205, 175, 255] : [170, 235, 255], c * .8));
      x.fillStyle = `rgba(${sc},${a})`; x.fillRect(px, d[1], d[2], d[2]);
      if (d[4] && d[2] > 1.2) { x.fillStyle = `rgba(${sc},${a * .35})`; x.fillRect(px - 2, d[1] + d[2] / 2 - .3, 4 + d[2], .6); x.fillRect(px + d[2] / 2 - .3, d[1] - 2, .6, 4 + d[2]); }
    }
    if (!shoot && Math.random() < .005) shoot = { x: Math.random() * W, y: Math.random() * H * .4, l: 0 };
    if (shoot) {
      shoot.l++; const sx2 = shoot.x + shoot.l * 9, sy2 = shoot.y + shoot.l * 3.2, g = x.createLinearGradient(sx2 - 90, sy2 - 32, sx2, sy2), sh = rgb(mix([255, 255, 255], [215, 180, 255], c));
      g.addColorStop(0, `rgba(${sh},0)`); g.addColorStop(1, `rgba(${sh},${.7 * (1 - shoot.l / 40)})`);
      x.strokeStyle = g; x.lineWidth = 1; x.beginPath(); x.moveTo(sx2 - 90, sy2 - 32); x.lineTo(sx2, sy2); x.stroke(); if (shoot.l > 40) shoot = null;
    }

    // Probe particles belong to the station; source and rules live in Details.
    for (let i = 1; i < 7; i++) {
      const sx = i * GAP + ox; if (sx < -GAP || sx > W + GAP || b.k === 'intro') continue;
      const near = Math.max(0, 1 - Math.abs(p - i) * 1.6);
      if (i === 2 && near > 0) for (let k = 0; k < 30; k++) { const an = k / 30 * 6.283 + t * .3, r = 52 + 16 * Math.sin(k * 1.7 + t); x.fillStyle = `rgba(230,235,250,${.6 * near})`; x.beginPath(); x.arc(sx + Math.cos(an) * r, CY + Math.sin(an) * r * .45, 1, 0, 7); x.fill(); }
    }

    const travelling = b.k !== 'intro' && b.k !== 'swoop' && b.k !== 'outro' && !b.blocked;
    const sy = CY - arc * 100, px = wx + ox;
    filament(ox, t, c, travelling ? px : W / 2, lc);

    // stations; their labels give way to the outro, which says the same once
    const labels = b.k === 'outro' ? 1 - clamp((t - b.t0 - .4) / 1.2) : 1;
    for (let i = 0; i < 7; i++) {
      const sx = i * GAP + ox; if (sx < -280 || sx > W + 280) continue;
      const here = b.k === 'dwell' && Math.abs(p - i) < .02, near = Math.max(0, 1 - Math.abs(p - i) * 1.6), rc = i >= 4 ? lc : '230,234,248';
      x.strokeStyle = `rgba(${rc},${.22 + .55 * near})`; x.lineWidth = 1; if (failing && i === 5) x.setLineDash([2, 4]);
      x.beginPath(); x.arc(sx, CY, 22, 0, 7); x.stroke(); x.setLineDash([]);
      x.strokeStyle = `rgba(${rc},${.06 + .18 * near})`; x.beginPath(); x.ellipse(sx, CY, 58, 20, -.18, 0, 7); x.stroke();
      const oa = t * .8 + i, co = Math.cos(-.18), si = Math.sin(-.18);
      x.fillStyle = `rgba(${rc},${.2 + .6 * near})`; x.beginPath(); x.arc(sx + Math.cos(oa) * 58 * co - Math.sin(oa) * 20 * si, CY + Math.cos(oa) * 58 * si + Math.sin(oa) * 20 * co, 1.4, 0, 7); x.fill();
      const hg = x.createLinearGradient(0, CY + 24, 0, CY + 72); hg.addColorStop(0, `rgba(${rc},${.05 + .2 * near})`); hg.addColorStop(1, `rgba(${rc},0)`);
      x.strokeStyle = hg; x.beginPath(); x.moveTo(sx, CY + 24); x.lineTo(sx, CY + 72); x.stroke();
      x.strokeStyle = `rgba(${rc},${.05 + .18 * near})`; x.beginPath(); x.arc(sx, CY + 80, 6, 0, 7); x.stroke();
      if (here && travelling) for (let r = 0; r < 2; r++) { const rr = 22 + ((u * 1.4 + r * .5) % 1) * 50; x.strokeStyle = `rgba(${rc},${.3 * (1 - (rr - 22) / 50)})`; x.beginPath(); x.arc(sx, CY, rr, 0, 7); x.stroke(); }
      txt(`${STATIONS[i][0]} — ${STATIONS[i][1].toUpperCase()}`, sx, CY + 120, 12, (.25 + .6 * near) * labels, 3);
      if (b.k !== 'intro' && b.k !== 'swoop') txt(subtitle(m, i, here ? b : {}, u), sx, CY + 140, 11, (.15 + .5 * near) * labels, 2);
      if (b.k !== 'intro') hits.push({ x: sx, y: CY, r: 34, id: 'st:' + i });
      if (focus === i) { x.strokeStyle = `rgba(${rc},.5)`; x.beginPath(); x.arc(sx, CY, 30 + Math.sin(t * 2) * 2, 0, 7); x.stroke(); }
      const S = window.Stations && window.Stations.get(i + 1);
      if (S && S.overlay && ((here && travelling) || focus === i)) {
        try {
          x.save();
          S.overlay({ ctx: x, cx: sx, cy: CY, t, u: focus === i ? 1 : u, c, lc, module: m, replay: R, focused: focus === i,
                      attempt: here && b.h !== undefined ? m.history[b.h] : m.history[m.history.length - 1],
                      txt, star, clamp, mix, rgb, W, H });
        } catch (err) { if (!S._warned) { S._warned = true; console.error(`station ${i + 1} overlay:`, err); } }
        finally { x.restore(); }
      }
    }

    // codebase cluster at Discover: programs still waiting their turn
    const dx = ox;
    const waiting = quietCaption ? [] : mods.map((q, i) => i).filter(i => i > mi || (i === mi && (b.k === 'swoop' || b.k === 'intro')));
    const cpos = i => [dx + CLUSTER[i % CLUSTER.length][0], CY + CLUSTER[i % CLUSTER.length][1]];
    x.setLineDash([2, 5]); x.strokeStyle = `rgba(${lc},.18)`;
    mods.forEach((q, i) => q.depends_on.forEach(d => { const j = mods.findIndex(z => z.id === d); if (j >= 0 && waiting.includes(i) && waiting.includes(j)) { const [a1, a2] = cpos(i), [b1, b2] = cpos(j); x.beginPath(); x.moveTo(a1, a2); x.lineTo(b1, b2); x.stroke(); } }));
    x.setLineDash([]);
    waiting.forEach(i => { const [qx, qy] = cpos(i); const blockedQ = (mods[i].error || '').startsWith('blocked') && i === mi;
      star(qx, qy, t + i, blockedQ ? .3 : .38, '215,222,240', '235,238,248', i); });

    // constellation at Verified: programs already accepted
    const vx = 6 * GAP + ox, vpos = i => [vx + CONST[i % CONST.length][0], CY + CONST[i % CONST.length][1]];
    const verified = quietCaption ? [] : mods.map((q, i) => i).filter(i => done(i) && !(i === mi && travelling));
    x.setLineDash([2, 5]); x.strokeStyle = `rgba(${lc},.28)`;
    mods.forEach((q, i) => q.depends_on.forEach(d => { const j = mods.findIndex(z => z.id === d); if (j >= 0 && verified.includes(i) && verified.includes(j)) { const [a1, a2] = vpos(i), [b1, b2] = vpos(j); x.beginPath(); x.moveTo(a1, a2); x.lineTo(b1, b2); x.stroke(); } }));
    x.setLineDash([]);
    verified.forEach(i => { const [qx, qy] = vpos(i); star(qx, qy, t + i, b.k === 'outro' ? .55 : .4, i % 2 ? '120,230,210' : rgb(mix([215, 225, 255], [185, 140, 255], c)), '235,228,255', i); });
    if (!quietCaption) mods.forEach((q, i) => { if (i < mi && q.status !== 'done' && !(q.error || '').startsWith('blocked')) { const fx = 5 * GAP + ox + 40 * (i - mi), fy = CY + 34; star(fx, fy, t, .22, '200,190,200', '220,215,220', i); txt(q.id.toUpperCase() + ' · FAILED', fx, fy + 22, 9, .4, 2); } });

    // the travelling star and its tail
    if (travelling) {
      trail.push([wx, sy]); if (trail.length > 55) trail.shift();
      for (let k = 1; k < trail.length; k++) { const a = k / trail.length, tc = rgb(mix([225, 232, 255], [120, 235, 215], c * (1 - a))); x.strokeStyle = `rgba(${tc},${a * a * .55})`; x.lineWidth = a * 2.4; x.beginPath(); x.moveTo(trail[k - 1][0] + ox, trail[k - 1][1]); x.lineTo(trail[k][0] + ox, trail[k][1]); x.stroke(); }
      const glow = failing ? '255,190,200' : rgb(mix([215, 225, 255], [185, 140, 255], c)), spk = failing ? '255,225,230' : rgb(mix([240, 244, 255], [230, 215, 255], c));
      const ended = b.failedEnd;
      if (!entrance) star(px, sy, t, ended ? .55 : b.working ? 1 + .14 * Math.sin(t * 4) : p > 5.98 ? 1.4 : moving ? 1.05 : 1, ended ? '190,185,195' : glow, ended ? '215,210,215' : spk, mi);
      if (ended) txt(`NOT VERIFIED AFTER ${m.attempts} ATTEMPTS`, px, sy - 40, 10, .55, 2.5);
    } else trail = [];
    const fo = ((ox * .55) % 1800 + 1800) % 1800;
    x.globalAlpha = .75; x.drawImage(fog, fo - 1800, H - 190); x.drawImage(fog, fo, H - 190); x.globalAlpha = 1;
    if (c > .02) { x.save(); x.globalCompositeOperation = 'multiply'; x.fillStyle = `rgb(${rgb(mix([255, 255, 255], [205, 170, 255], c))})`; x.fillRect(-10, H - 190, W + 20, 190); x.restore(); }
    x.restore();

    if (!panel.classList.contains('open')) narration(t, ox, lc, b, u);  // an open readout already says it
    leader(t, ox, lc);

    // intro and outro type
    if (b.k === 'intro') {
      const a = clamp((t - .3) / .9) * clamp((b.t1 - t) / .8);
      txt('NorthBound', W / 2, 70, 26, .9 * a, 8, 'center', '240,240,246', '300');
      txt(`${n} COBOL PROGRAM${n > 1 ? 'S' : ''}  ·  ${R.title.toUpperCase()}`, W / 2, 98, 10, .5 * a, 4);
    }
    if (b.k === 'outro' && !panel.classList.contains('open')) {
      const a = clamp((t - b.t0 - .4) / 1.2), ok = mods.filter(q => q.status === 'done').length;
      const total = mods.reduce((s, q) => s + (q.status === 'done' ? q.tests_total : 0), 0), only = n === 1 && ok === 1 && m;
      txt(only ? 'VERIFIED' : `${ok} / ${n} VERIFIED`, W / 2, H - 116, 20, .9 * a, 8, 'center', '245,246,252', '300');
      txt(only ? `${(m.file || m.id).toUpperCase()} → ${m.id.toUpperCase()}.PY  ·  ${m.tests_passed} / ${m.tests_total} OUTPUTS MATCH THE REAL COBOL`
        : `${total} RECORDED OUTPUTS · EVERY ONE MATCHES THE REAL COBOL`, W / 2, H - 90, 10, .6 * a, 3.5);
    }
    // the code can be taken from the moment the last program is verified, and stays through the summary
    showGetCode((b.k === 'outro' || (mi === n - 1 && b.k !== 'swoop' && p > 5.98 && m.status === 'done')) && !panel.classList.contains('open'));

    if (fr % 3 === 0) grain();
    x.globalAlpha = .06 * (1 - c * .5); x.fillStyle = x.createPattern(grainC, 'repeat'); x.fillRect(0, 0, W, H); x.globalAlpha = 1;
    const vg = x.createRadialGradient(W / 2, H / 2, H * .2, W / 2, H / 2, W * .75);
    vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, `rgba(${rgb(mix([0, 0, 0], [8, 2, 20], c))},.8)`);
    x.fillStyle = vg; x.fillRect(0, 0, W, H);

    if (b.blocked && !panel.classList.contains('open')) txt('BLOCKED', 24, 30, 11, .5, 3, 'left');
    const label = R.live ? `LIVE  ·  ${R.mode === 'offline_fixture' ? 'OFFLINE FIXTURE (NO MODEL CALLS)' : 'REAL NEMOTRON RUN'}${R.finished ? '  ·  FINISHED' : ''}`
      : R.kind === 'mutation' ? 'CONTROLLED MUTATION  ·  PLANTED BUG, NOT A MODEL OUTPUT'
      : R.mode === 'real_model' ? `REPLAY OF A REAL NEMOTRON RUN${m && m.run_note ? '  ·  ' + m.run_note.toUpperCase() : ''}` : 'OFFLINE FIXTURE REPLAY';
    // Keep the honest replay disclosure above the toolbar, even when its buttons wrap.
    const footerY = Math.min(H - 22, H - (playBtn.parentElement.offsetHeight + 34) / K);
    const footerLines = wrap(label, W - 48, 9, 2.5);
    if (!panel.classList.contains('open')) footerLines.forEach((line, i) => txt(line, W - 24, footerY - (footerLines.length - 1 - i) * 13, 9, .32, 2.5, 'right'));
  }

  // ---------- the verified Python, to take away (under the outro) ----------
  const getCode = document.getElementById('get-code');
  // a dropped zip gets its whole codebase back as Python (<zip>-modernized.zip), from the recorded run
  const verifiedFiles = () => ((SIM ? SIM.full : R) || { modules: [] }).modules
    .filter(q => q.status === 'done' && q.python).map(q => [`${q.id}.py`, q.python]);
  function showGetCode(on) {
    on = on && verifiedFiles().length > 0;
    if (getCode.hidden === on) getCode.hidden = !on;
    if (on) getCode.style.top = `${(H - 64) * K}px`;  // under the outro's two lines, in canvas units
  }
  getCode.onclick = () => {
    const files = verifiedFiles(); if (!files.length) return;
    const stem = SIM && SIM.file ? SIM.file.replace(/\.zip$/i, '') : null, one = files.length === 1 && !stem, a = document.createElement('a');
    const folder = stem ? `${stem}-modernized` : 'modernized-python';
    a.href = URL.createObjectURL(one ? new Blob([files[0][1]], { type: 'text/x-python' }) : zip(files.map(([n, py]) => [`${folder}/${n}`, py])));
    a.download = one ? files[0][0] : `${folder}.zip`;
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  const CRC = Array.from({ length: 256 }, (_, n) => { for (let k = 0; k < 8; k++) n = n & 1 ? 0xedb88320 ^ (n >>> 1) : n >>> 1; return n >>> 0; });
  function zip(files) {  // stored, not compressed: a few small text files need no library
    const enc = new TextEncoder(), body = [], dir = []; let off = 0;
    const rec = (n, fill) => { const v = new DataView(new ArrayBuffer(n)); fill(v); return new Uint8Array(v.buffer); };
    for (const [name, text] of files) {
      const nm = enc.encode(name), data = enc.encode(text);
      let c = ~0; for (const byte of data) c = CRC[(c ^ byte) & 255] ^ (c >>> 8); c = ~c >>> 0;
      const common = (v, at) => {  // version, UTF-8 names, stored, 1980-01-01, crc, sizes, name length
        [20, 0x800, 0, 0, 33].forEach((x16, i) => v.setUint16(at + 2 * i, x16, true));
        v.setUint32(at + 10, c, true); v.setUint32(at + 14, data.length, true); v.setUint32(at + 18, data.length, true); v.setUint16(at + 22, nm.length, true);
      };
      body.push(rec(30, v => { v.setUint32(0, 0x04034b50, true); common(v, 4); }), nm, data);
      dir.push(rec(46, v => { v.setUint32(0, 0x02014b50, true); v.setUint16(4, 20, true); common(v, 6); v.setUint32(42, off, true); }), nm);
      off += 30 + nm.length + data.length;
    }
    const size = dir.reduce((s, part) => s + part.length, 0);
    const end = rec(22, v => { v.setUint32(0, 0x06054b50, true); v.setUint16(8, files.length, true); v.setUint16(10, files.length, true); v.setUint32(12, size, true); v.setUint32(16, off, true); });
    return new Blob([...body, ...dir, end], { type: 'application/zip' });
  }

  // ---------- side panel ----------
  const panel = document.getElementById('panel'), pBody = document.getElementById('p-body'), pTabs = document.getElementById('p-tabs');
  let pMod = null, pTab = 'cobol', pStar = null;  // pStar: the module whose star the readout points at
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
  const TABS = [['cobol', 'COBOL'], ['python', 'Python'], ['spec', 'Spec'], ['tests', 'Answer key'], ['attempts', 'Attempts']];
  function hold(worldX) {  // pause the replay while a readout is open; resume on close if it was playing
    travel = null;
    if (focusX === null) resumeAfter = playing;
    playing = false; playBtn.textContent = 'Play'; focusX = worldX;
  }
  function openPanel(i, worldX) {
    focus = null; pBody.classList.remove('still'); if (worldX !== undefined) hold(worldX);
    pMod = R.modules[i]; pStar = i; document.getElementById('p-title').textContent = pMod.file || pMod.id;
    const st = pMod.status === 'done' ? `verified · ${pMod.tests_passed}/${pMod.tests_total}` : (pMod.error || pMod.status);
    document.getElementById('p-meta').textContent = `${pMod.kind} · ${st} · ${pMod.attempts} attempt${pMod.attempts === 1 ? '' : 's'}`;
    pTabs.innerHTML = TABS.map(([k, l]) => `<button data-k="${k}" class="${k === pTab ? 'on' : ''}">${l}</button>`).join('');
    pTabs.style.display = ''; pTabs.onclick = programTabs;
    renderTab(); panel.classList.remove('station'); panel.classList.add('open'); panel.setAttribute('aria-hidden', 'false');
  }
  function closePanel() {
    panel.classList.remove('open', 'station'); panel.setAttribute('aria-hidden', 'true'); pStar = null;
    if (focusX !== null) { focus = null; focusX = null; if (resumeAfter) { playing = true; playBtn.textContent = 'Pause'; } }
  }
  // a station panel: that step's real output for the program on screen (web/stations/*.js)
  let stationTab = 0;
  // re-render the open readout with the latest data, keeping its tab and scroll (a replay that is playing)
  function refreshPanel() {
    const top = pBody.scrollTop; pBody.classList.add('still');  // update in place: no drift-in replay
    if (panel.classList.contains('station') && focus !== null) openStation(focus, true);
    else if (pStar !== null && R.modules[pStar]) { pMod = R.modules[pStar]; renderTab(); }
    pBody.scrollTop = top;
  }
  function openStation(i, refresh = false) {
    const S = window.Stations && window.Stations.get(i + 1);
    const b = beatAt(Math.min(clock, TL.end - 1e-3)), mi = b.mi !== undefined ? b.mi : (b.k === 'outro' ? R.modules.length - 1 : 0);
    const m = R.modules[mi];
    if (!refresh) { hold(i * GAP); stationTab = 0; pBody.classList.remove('still'); }
    focus = i; pStar = null; capFocus = null;
    document.getElementById('p-title').textContent = `${STATIONS[i][0]} — ${STATIONS[i][1]}`;
    document.getElementById('p-meta').textContent = `${m.file || m.id} · ${m.kind}${S && S.agent ? ' · ' + S.agent : ''}`;
    let out;
    try { out = S ? S.render({ module: m, replay: R, H: window.Stations.H }) : window.Stations.H.empty('No view for this station yet.'); }
    catch (err) { console.error(`station ${i + 1} render:`, err); out = window.Stations.H.empty('This view hit an error. See the console.'); }
    const tabs = out && typeof out === 'object' && Array.isArray(out.tabs) ? out.tabs : null;
    pTabs.style.display = tabs && tabs.length > 1 ? '' : 'none';
    const show = k => { stationTab = k; setBody(tabs ? tabs[k].html : String(out || ''));
      [...pTabs.children].forEach((bn, j) => bn.classList.toggle('on', j === k)); };
    pTabs.innerHTML = tabs ? tabs.map((tb, j) => `<button data-st="${j}">${esc(tb.label)}</button>`).join('') : '';
    pTabs.onclick = e => { const k = e.target.dataset && e.target.dataset.st; if (k !== undefined) show(+k); };
    show(tabs ? Math.min(stationTab, tabs.length - 1) : 0); panel.classList.add('open', 'station'); panel.setAttribute('aria-hidden', 'false');
  }
  const programTabs = e => { const k = e.target.dataset && e.target.dataset.k; if (!k) return; pTab = k; [...pTabs.children].forEach(bn => bn.classList.toggle('on', bn.dataset.k === k)); renderTab(); };
  document.getElementById('p-close').onclick = closePanel;
  // the program readout uses the same building blocks as the stations, so the two never drift apart
  const COBOL_LOGIC = /\b(IF|EVALUATE|WHEN|COMPUTE|MOVE|ADD|SUBTRACT|MULTIPLY|DIVIDE|PERFORM|CALL|DISPLAY|ACCEPT)\b/i;
  const PY_KEY = /^\s*def (main|call)\b|ROUND_|quantize|^\s*import |^\s*from \S+ import /;
  const linesWhere = (src, re, skip) => String(src || '').split('\n').map((l, k) => (!skip || !skip(l)) && re.test(l) ? k + 1 : 0).filter(Boolean);
  const cobolComment = l => l.length > 6 && l[6] === '*' || /^\s*\*>/.test(l);
  function setBody(html) {
    pBody.innerHTML = html; pBody.scrollTop = 0;
    [...pBody.children].forEach((el, k) => el.style.setProperty('--i', Math.min(k, 12)));
  }
  function renderTab() {
    const m = pMod, H = window.Stations.H; let h = '';
    if (pTab === 'cobol') h = m.cobol ? H.text('Bright lines carry the logic.') + H.code(m.cobol, { highlight: linesWhere(m.cobol, COBOL_LOGIC, cobolComment) }) : H.empty('Source not in this replay.');
    if (pTab === 'python') h = m.python ? H.text('Bright lines are the entry points and the COBOL number rules.') + H.code(m.python, { highlight: linesWhere(m.python, PY_KEY) }) : H.empty('Not written yet.');
    if (pTab === 'spec') {
      const sp = m.spec || {};
      h = sp.summary ? H.section('Summary', H.text(sp.summary)) : H.empty('No spec was recorded for this program.');
      for (const [k, l] of [['business_rules', 'Business rules'], ['edge_cases', 'Edge cases'], ['quirks', 'COBOL quirks']])
        if ((sp[k] || []).length) h += H.section(l, H.list(sp[k].map(r => typeof r === 'string' ? r : JSON.stringify(r)), k === 'business_rules'));
    }
    if (pTab === 'tests') {
      const g = m.golden || [], bad = new Set((m.history || []).flatMap(a => (a.failures || []).map(f => f.input)));
      h = g.length ? H.section('Recorded from the real COBOL', H.table(['Input', 'Output'], g.slice(0, 40).map(c => [c.input, c.output]), { tone: k => bad.has(g[k].input) ? 'bad' : '' }))
        : H.empty('No answer key in this replay.');
    }
    if (pTab === 'attempts') {
      h = (m.history || []).map(a => {
        let body = H.dots([...Array(a.passed || 0).fill('ok'), ...Array(Math.max(0, (a.total || 0) - (a.passed || 0))).fill('bad')]) + H.text(`${a.passed} of ${a.total} match.`);
        (a.failures || []).slice(0, 3).forEach(f => { body += H.text(`Input ${f.input === '' ? '(empty)' : f.input}`) + H.diff(f.expected, f.actual); });
        if (a.explanation && a.explanation.reason) body += H.quote(a.explanation.reason, `Nemotron · ${a.explanation.verdict === 'legacy_quirk' ? 'COBOL quirk' : 'new code bug'}`);
        return H.section(`Attempt ${a.attempt}`, body);
      }).join('') || H.empty('No attempts recorded.');
      if ((m.unit_tests_quarantined || []).length) h += H.section('Unit tests held for review', H.list(m.unit_tests_quarantined));
    }
    setBody(h);
    const hi = (pTab === 'cobol' || pTab === 'python') && pBody.querySelector('.st-hi');
    if (hi) pBody.scrollTop = Math.max(0, hi.offsetTop - pBody.offsetTop - 90);
  }
  function hitAt(e) {
    const r = cv.getBoundingClientRect(), mx = (e.clientX - r.left) / K, my = (e.clientY - r.top) / K;
    const near = hits.filter(hh => Math.hypot(hh.x - mx, hh.y - my) < hh.r);
    const det = near.find(hh => String(hh.id).startsWith('det:')), ring = near.find(hh => String(hh.id).startsWith('st:'));
    const star = near.find(hh => typeof hh.id === 'number');
    // DETAILS first; the travelling star parked on a ring means "this step", so the ring wins; other stars open their program
    return det || (ring && (!star || star.id === moduleNow()) ? ring : star || ring);
  }
  cv.addEventListener('click', e => {
    if (entrance) return;
    const hh = hitAt(e); if (!hh) { closeCaption(); return closePanel(); }
    if (typeof hh.id === 'string' && hh.id.startsWith('det:')) openStation(+hh.id.slice(4));
    else if (typeof hh.id === 'string') openCaption(+hh.id.slice(3));
    else openPanel(hh.id, hh.x - (W / 2 - cam));  // the star's world position, so the camera can frame it
  });
  cv.addEventListener('mousemove', e => cv.classList.toggle('pointer', !!hitAt(e)));

  // ---------- loading: recordings, the intake, live runs ----------
  const sel = document.getElementById('replay'), intake = document.getElementById('intake');
  const fallbackBtn = document.getElementById('fallback'), backBtn = document.getElementById('backlive');
  const runLiveBtn = document.getElementById('run-live-instead'), quickBtn = document.getElementById('quick-live');
  skipBtn.onclick = () => skipToReview();
  // one standalone program (nothing it calls) migrated live: real Nemotron calls in about 40 seconds
  function offerQuickLive(codebase) {
    // the live proof runs a program that stands alone and verified on its first try, never one that needed a person
    // (a recording can name its tested choice: quick_live; the bank's is LOANPAY, live-tested 10 times on Nov 8)
    const mods = (R && R.modules) || [], alone = m => m.kind !== 'subprogram' && !(m.depends_on || []).length;
    const pick = mods.find(m => m.id === (R && R.quick_live) && alone(m))
      || mods.find(m => alone(m) && m.status === 'done' && (m.history || []).length <= 1 && !(m.human_hints || []).length);
    quickBtn.hidden = !(API && API.live && codebase && pick);
    quickBtn.onclick = () => startLive(codebase, R && R.name, { only: pick.id, quick: true });
  }
  let uploadVersion = 0;
  let API = null, pollTimer = null, liveSession = null, recordings = [];
  const caseFile = document.getElementById('case');
  function intakeOpen() { return intake.classList.contains('open') || caseFile.classList.contains('open'); }
  // the case file: the real-world problem, before the codebase goes in
  function openCase() {
    cancelEntrance();
    uploadVersion++;
    travel = null; resumeAfter = false;
    playing = false; playBtn.textContent = 'Play'; closePanel(); closeCaption(); intake.classList.remove('open'); intake.setAttribute('aria-hidden', 'true');
    caseFile.classList.add('open'); caseFile.setAttribute('aria-hidden', 'false'); document.body.classList.add('intake-on');
    caseFile.scrollTop = 0;
    history.replaceState(null, '', '#case');
  }
  function closeCase() { caseFile.classList.remove('open'); caseFile.setAttribute('aria-hidden', 'true'); }
  document.getElementById('case-go').onclick = () => { closeCase(); openIntake(); };
  document.getElementById('in-back').onclick = () => { openCase(); };
  function normalize(rep) { (rep.modules || []).forEach(q => { q.depends_on = q.depends_on || []; q.history = q.history || []; }); return rep; }
  function stopLive() { skipBtn.hidden = true; cancelEntrance(); SIM = null; travel = null; clearTimeout(pollTimer); pollTimer = null; liveSession = null; fallbackBtn.hidden = true; }
  // a run still going on the server: offer the way back to it from a recording or the intake
  async function runningSession() {
    if (!API) return null;
    try { return (await (await fetch('api/status', { cache: 'no-store' })).json()).running || null; } catch (err) { return null; }
  }
  async function offerBackToLive() {
    const s = await runningSession();
    backBtn.hidden = !s || liveSession === s;
    backBtn.onclick = () => { if (s) attach(s); };
  }
  async function load(name, demo = null) {
    const version = ++uploadVersion;
    runLiveBtn.hidden = true; runLiveBtn.onclick = null; quickBtn.hidden = true;
    stopLive(); const lv = sel.querySelector('option[value="__live"]'); if (lv) lv.remove();
    const res = await fetch(`replays/${name}.json`, { cache: 'no-store' }); if (!res.ok) throw new Error(`replay ${name}: ${res.status}`);
    const rep = await res.json();
    if (version !== uploadVersion) return;
    SIM = null;
    R = normalize(rep);
    TL = buildTimeline(R); restart();
    if (demo && intake.classList.contains('open')) {
      if (!await startEntrance() || version !== uploadVersion) return;
    }
    document.getElementById('loading').style.display = 'none'; closeIntake();
    if ([...sel.options].some(o => o.value === name)) sel.value = name;
    history.replaceState(null, '', `#${name}`);
    offerQuickLive((demo && demo.codebase) || R.codebase);
    if (demo) {
      startSim(R, demo.file);  // the dropped codebase runs through, step by step, from the recording
      runLiveBtn.hidden = !demo.codebase;
      runLiveBtn.onclick = () => { openIntake(); startLive(demo.codebase, name); };
    }
    offerBackToLive();
  }
  sel.onchange = () => load(sel.value).catch(showError);
  function showError(err) { const l = document.getElementById('loading'); l.style.display = 'grid'; l.textContent = String(err.message || err); }

  // a live run: poll the server for what the session has written so far and keep the timeline growing
  function applyLive(rep) {
    rep = normalize(rep);
    const prevWork = TL && TL.beats.find(b => b.working);
    R = rep; TL = rep.finished ? buildTimeline(rep) : liveTimeline(rep);
    if (prevWork && clock > prevWork.t0) {  // the step it was waiting on finished: play it from its arrival
      const nb = beatAt(prevWork.t0 + .01);
      if (!nb.working || nb.mi !== prevWork.mi || nb.at !== prevWork.at || nb.h !== prevWork.h) clock = prevWork.t0;
    }
    fallbackBtn.hidden = !rep.recording || rep.finished;
    document.getElementById('loading').style.display = 'none';
  }
  async function poll() {
    if (!liveSession) return;
    try {
      const r = await fetch(`api/runs/${liveSession}/replay`, { cache: 'no-store' });
      if (r.status === 200) { const rep = await r.json(); applyLive(rep); if (rep.finished) { liveSession = null; return; } }
      else if (r.status !== 202) throw new Error(`live run: ${r.status}`);
    } catch (err) { note(`Lost the live run (${err.message}). You can switch to the recording.`, true); }
    pollTimer = setTimeout(poll, 700);
  }
  async function startLive(codebase, recording, opts = {}) {
    const version = ++uploadVersion; runLiveBtn.hidden = true; runLiveBtn.onclick = null; quickBtn.hidden = true;
    note(opts.only ? `Starting a live run of ${opts.only.toUpperCase()}…` : 'Starting a real Nemotron run…');
    let r;
    try { r = await fetch('api/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ codebase, ...opts }) }); }
    catch (err) { if (version === uploadVersion) note('The local server is not reachable.', true); return; }
    const body = await r.json().catch(() => ({}));
    if (version !== uploadVersion) return;
    if (!r.ok) {
      note(body.error || 'The run could not start.', true);
      if (recording) setTimeout(() => { if (version === uploadVersion) load(recording).catch(showError); }, 1600);
      return;
    }
    attach(body.session);
  }
  // follow a run (started here, or from the terminal: open the page at #live=<session>)
  function attach(session) {
    uploadVersion++; runLiveBtn.hidden = true; runLiveBtn.onclick = null; quickBtn.hidden = true;
    stopLive(); liveSession = session; backBtn.hidden = true; chase = true;
    R = null; TL = null; workSince.clear(); clock = 0; cam = 0; trail = []; closePanel(); closeCaption(); playing = true; playBtn.textContent = 'Pause';
    closeIntake(); const l = document.getElementById('loading'); l.textContent = 'Copying the codebase…'; l.style.display = 'grid';
    history.replaceState(null, '', `#live=${session}`);
    if (![...sel.options].some(o => o.value === '__live')) sel.insertAdjacentHTML('afterbegin', '<option value="__live" disabled>Live run</option>');
    sel.value = '__live';
    fallbackBtn.onclick = () => { const rec = R && R.recording; if (rec) load(rec).catch(showError); };
    poll();
  }

  // the intake: pick a codebase or drop a zip of one
  function note(text, bad) { const n = document.getElementById('in-note'); n.textContent = text || ''; n.classList.toggle('bad', !!bad); }
  function openIntake() {
    cancelEntrance(); uploadVersion++; travel = null; resumeAfter = false; closeCase();
    playing = false; playBtn.textContent = 'Play'; closePanel(); closeCaption();
    intake.classList.add('open'); intake.setAttribute('aria-hidden', 'false'); intake.scrollTop = 0;
    document.body.classList.add('intake-on');
    history.replaceState(null, '', location.pathname + location.search);
    document.getElementById('loading').style.display = 'none';
    note(''); renderIntake(); syncPlayback();
    document.getElementById('northbound-title').focus({ preventScroll: true });
  }
  function closeIntake() { closeCase(); intake.classList.remove('open'); intake.setAttribute('aria-hidden', 'true'); document.body.classList.remove('intake-on'); note(''); }
  document.getElementById('intake-btn').onclick = openIntake;
  document.getElementById('case-home').onclick = openIntake;
  document.getElementById('panel-home').onclick = openIntake;
  function renderIntake() {
    document.getElementById('in-foot').textContent = API
      ? 'COBOL → Python · every recorded output must match'
      : 'Uploads need the local demo server';
  }
  const drop = document.getElementById('drop'), dropFile = document.getElementById('drop-file');
  async function upload(file) {
    if (!file) return;
    if (!/\.zip$/i.test(file.name)) return note('Drop a .zip of COBOL files (.cbl, .cob, .cpy).', true);
    if (!API) return note('Uploads need the local server: python tools/serve.py.', true);
    cancelEntrance();
    const version = ++uploadVersion;
    runLiveBtn.hidden = true; runLiveBtn.onclick = null; quickBtn.hidden = true;
    note(`Reading ${file.name}…`);
    const r = await fetch('api/upload', { method: 'POST', headers: { 'Content-Type': 'application/zip', 'X-Filename': file.name }, body: file }).catch(() => null);
    const body = r ? await r.json().catch(() => ({})) : {};
    if (version !== uploadVersion) return;
    if (!r || !r.ok) return note(body.error || 'Upload failed.', true);
    if (body.recording) {
      note(`${body.title} recognised. Playing a recorded real run.`);
      await new Promise(resolve => setTimeout(resolve, 1200));
      if (version !== uploadVersion) return;
      speed = 1; document.getElementById('speed').value = '1';
      return load(body.recording, { codebase: body.codebase, file: file.name }).catch(showError);
    }
    note(`${body.files} COBOL files found. Starting…`);
    startLive(body.codebase, null);
  }
  dropFile.onchange = () => { const file = dropFile.files[0]; dropFile.value = ''; upload(file); };
  drop.onkeydown = e => {
    if (e.key === 'Enter' || e.code === 'Space') { e.preventDefault(); dropFile.click(); }
  };
  ['dragenter', 'dragover'].forEach(ev => intake.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => intake.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
  intake.addEventListener('drop', e => upload(e.dataTransfer && e.dataTransfer.files[0]));

  (async () => {
    try { const r = await fetch('api/status', { cache: 'no-store' }); API = r.ok ? await r.json() : null; } catch (err) { API = null; }
    try { recordings = await (await fetch('replays/index.json', { cache: 'no-store' })).json(); } catch (err) { recordings = []; }
    sel.innerHTML = recordings.map(r => `<option value="${esc(r.name)}">${esc(r.title)}</option>`).join('');
    const want = location.hash.slice(1), follow = /^live=([0-9a-z-]+)$/.exec(want);
    if (follow && API) return attach(follow[1]);
    if (recordings.some(r => r.name === want)) return load(want);
    document.getElementById('loading').style.display = 'none';
    if (want === 'case') openCase(); else openIntake();  // Home is the default; #codebases remains a landing-page alias
  })().catch(showError);
  requestAnimationFrame(frame);
  // for rehearsing a moment: galaxy.seek(seconds), galaxy.t
  window.galaxy = { seek(s) { travel = null; clock = Math.max(0, s); trail = []; lastFail = null; cam = (beatAt(clock).k === 'move' ? beatAt(clock).a : (beatAt(clock).at || 0)) * GAP;
                             for (let i = 0; i < 90; i++) { x.setTransform(DPR * K, 0, 0, DPR * K, 0, 0); x.save(); draw(clock); x.restore(); } }, get t() { return clock; },
                    get beats() { return TL && TL.beats.map(b => [b.k, b.mi, b.at, +b.t0.toFixed(1), b.fail || false]); },
                    runRecording(name, file) { return load(name, { codebase: null, file }); },  // the drop path, without a file
                    // what a recording shows right now (web/hints.js replays a person's hint from it)
                    view() { return R && TL && !R.live ? { R, TL, full: SIM ? SIM.full : R, beat: beatAt(Math.min(clock, TL.end - 1e-3)), clock,
                      sim: !!SIM, hintSent: !!(SIM && SIM.hintSent), typedHint: SIM && SIM.typedHint } : null; },
                    sendHint(text) { sendHint(text); },
                    // a live run right now (web/reveal.js shows its COBOL and new Python once it is verified)
                    liveView() { return R && TL && R.live ? { R, beat: beatAt(Math.min(clock, TL.end - 1e-3)), clock } : null; },
                    // rehearsal: jump a running replay to just before its n-th real event (e.g. SETTLE's first)
                    skipToReview() { skipToReview(); },
                    simTo(n) { if (!SIM) return; SIM.n = Math.max(0, Math.min(n, SIM.end)); SIM.hintSent = false; simApply();
                               const w = TL.beats.find(b => b.working); clock = w ? w.t0 : clock; trail = []; lastFail = null; playing = true; syncPlayback(); },
                    get sim() { return SIM && { revealed: SIM.n, events: SIM.full.events.length }; },
                    get hits() { return hits.map(h => ({ id: h.id, x: h.x * K, y: h.y * K })); } };  // css px, for rehearsal checks
})();
