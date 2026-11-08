/* Legacy → Verified: replays a recorded run as a star travelling through the pipeline.
   Everything on screen comes from web/replays/<name>.json (exported by tools/export_replay.py).
   Black and white is old COBOL; colour (aurora) arrives as the program becomes verified Python. */
(() => {
  'use strict';
  const cv = document.getElementById('sky'), x = cv.getContext('2d');
  const MONO = 'ui-monospace, "SF Mono", Menlo, Consolas, monospace';
  const BASE_H = 520, GAP = 560, CY = 252;
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
      });
      if (m.status === 'done') { mv(6); push({ k: 'dwell', mi, at: 6, done: true }, talk(6, 3)); }
      else push({ k: 'dwell', mi, at: 5, failedEnd: true }, 3.6);
    });
    push({ k: 'outro' }, 6);
    return { beats, end: t };
  }
  const READ = 4.2;  // seconds a narrated stop holds
  function beatAt(t) {
    const b = TL.beats; let lo = 0, hi = b.length - 1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (b[mid].t1 < t) lo = mid + 1; else hi = mid; }
    return b[lo];
  }

  // ---------- playback ----------
  let clock = 0, last = performance.now(), speed = 1, playing = true, focus = null, resumeAfter = false, focusX = null;  // focusX: world x the open readout is about
  let cam = 0, cs = 0, trail = [], fr = 0, shoot = null, hits = [];
  const playBtn = document.getElementById('play');
  playBtn.onclick = () => { playing = !playing; playBtn.textContent = playing ? 'Pause' : 'Play'; playBtn.setAttribute('aria-label', playBtn.textContent); };
  document.getElementById('restart').onclick = restart;
  document.getElementById('speed').onchange = e => { speed = +e.target.value; };
  function restart() { clock = 0; cam = 0; cs = 0; trail = []; }
  addEventListener('keydown', e => {
    if (e.target.tagName === 'SELECT') return;
    if (intakeOpen()) { if (e.key === 'Escape' && R) closeIntake(); return; }
    if (e.code === 'Space') { e.preventDefault(); playBtn.click(); }
    if (e.key === 'r' || e.key === 'R') restart();
    if (e.key === 'Escape') { if (panel.classList.contains('open')) closePanel(); else closeCaption(); }
    if ((e.key === 'Enter' || e.key === 'd' || e.key === 'D') && capFocus !== null) openStation(capFocus);
    if (/^[1-7]$/.test(e.key) && R) { const n = +e.key - 1; if (capFocus === n && !panel.classList.contains('open')) openStation(n); else openCaption(n); }
    if (e.key === 'ArrowRight') clock = Math.min(TL.end, clock + 3);
    if (e.key === 'ArrowLeft') { clock = Math.max(0, clock - 3); trail = []; }
  });

  // ---------- module text for the scene ----------
  function sceneText(m) {
    const cob = (m.cobol || '').split('\n').map(l => l.replace(/\s+$/, '')).filter(l => l.trim() && !/^\s{6}\*/.test(l));
    const p = cob.findIndex(l => /PROCEDURE\s+DIVISION/i.test(l));
    const py = (m.python || '').split('\n').filter(l => l.trim() && !l.trim().startsWith('#'));
    let q = py.findIndex(l => /^def (main|call)\b/.test(l)); if (q < 0) q = 0;
    const rules = ((m.spec && m.spec.business_rules) || []).slice(0, 5);
    return {
      cobol: cob.slice(Math.max(0, p), Math.max(0, p) + 8).map(l => clip(l.trim() ? l.slice(Math.min(7, l.search(/\S/))) : l, 46)),
      python: py.slice(q, q + 8).map(l => clip(l, 46)),
      rules: rules.map(r => clip(r, 58)),
    };
  }

  function subtitle(m, i, b, u) {
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
  function drawAurora(t, c) {
    if (c < .02) return;
    const w = aur.width, h = aur.height, sx = w / W, sy = h / H;
    ax.setTransform(1, 0, 0, 1, 0, 0); ax.clearRect(0, 0, w, h); ax.setTransform(sx, 0, 0, sy, 0, 0);
    const curtains = [[0, .55, [120, 255, 200], [150, 90, 255]], [.33, .42, [170, 110, 255], [90, 200, 255]], [.7, .5, [110, 240, 210], [200, 120, 255]]];
    for (const [off, amp, top, bot] of curtains) {
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
  let capFocus = null, capOn = 0;
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
    if (b.k === 'dwell' && b.working) return { n: b.at, mi: b.mi, a: clamp((t - b.t0 - .35) / .55), since: b.t0 + .35, ai: b.h || 0, working: true };
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
    const s = Math.floor((performance.now() - workSince.get(key)) / 1000), clock = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
    const say = {
      0: 'Mapping the codebase: which programs call which.',
      1: 'Nemotron is reading the COBOL and writing down what it does.',
      2: 'Nemotron is inventing test inputs. Then the real COBOL records the answers.',
      4: ac.ai > 0 ? 'Nemotron is fixing the Python, using the cases it got wrong.' : 'Nemotron is writing the Python.',
      5: 'Running every test against the original COBOL.',
      6: 'Writing unit tests for the verified Python.',
    }[ac.n] || 'Working.';
    return { sentence: say, proof: { kind: 'line', text: `LIVE   ·   ${clock}` } };
  }
  function narration(t, ox, lc, b, u) {
    const ac = activeCaption(t, b, u);
    capOn = ac ? ac.a : 0; if (!ac || ac.a < .01) return;
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
    const y0 = right ? CY - 152 : 76;  // compact: below the corner labels, above the ring
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
    if (intakeOpen()) { try { x.setTransform(DPR * K, 0, 0, DPR * K, 0, 0); x.globalAlpha = 1; drawSky(now / 1000); } catch (err) { console.error(err); } return; }
    // a live run joined late catches up at double speed until it is close to what's happening now
    const edge = R && R.live && TL && TL.beats.find(q => q.working), catchUp = edge && edge.t0 - clock > 15 ? Math.max(speed, 2) : speed;
    if (R && playing) clock = Math.min(TL.end + 2, clock + dtReal * catchUp);
    if (R) { try { x.setTransform(DPR * K, 0, 0, DPR * K, 0, 0); x.globalAlpha = 1; x.save(); draw(clock); } catch (err) { if (!frame.warned) { frame.warned = true; console.error(err); } } finally { x.restore(); } }
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
    const fo = ((ox * .55) % 1800 + 1800) % 1800; x.globalAlpha = .75; x.drawImage(fog, fo - 1800, H - 190); x.drawImage(fog, fo, H - 190); x.globalAlpha = 1;
    if (fr % 3 === 0) grain(); x.globalAlpha = .06; x.fillStyle = x.createPattern(grainC, 'repeat'); x.fillRect(0, 0, W, H); x.globalAlpha = 1;
    const vg = x.createRadialGradient(W / 2, H / 2, H * .2, W / 2, H / 2, W * .75); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,.8)');
    x.fillStyle = vg; x.fillRect(0, 0, W, H);
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
      if (!evs.length) { work({ k: 'dwell', mi, at: 0 }); break; }
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
      }
      if (stop) break;
      if (over) continue;
      if (has('accept')) { mv(6); push({ k: 'dwell', mi, at: 6, done: true }, talk(6, 3)); continue; }
      if (failed) { push({ k: 'dwell', mi, at: 5, failedEnd: true }, 3.6); continue; }
      mv(6); work({ k: 'dwell', mi, at: 6 }); break;
    }
    return { beats, end: t };
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
    const roomy = W > 760, starAt = roomy ? W * .36 : W / 2;  // left of centre leaves the right side for the caption
    const freeMid = panel.classList.contains('open') ? (innerWidth - panel.getBoundingClientRect().width) / 2 / K : starAt;
    const wx = p * GAP, camT = focusX !== null ? focusX + W / 2 - freeMid : wx + W / 2 - starAt;
    cam += (camT - cam) * (focusX !== null ? .08 : b.k === 'swoop' ? .12 : .055);
    const ox = W / 2 - cam, lc = rgb(mix([225, 230, 245], [195, 170, 255], c));

    x.save(); x.translate(jit, 0);
    x.fillStyle = `rgb(${rgb(mix([7, 7, 10], [10, 6, 22], c))})`; x.fillRect(-10, 0, W + 20, H);
    const mo = ((ox * .12) % 2400 + 2400) % 2400;
    x.globalAlpha = 1 - c; x.drawImage(milkyG, mo - 2400, 0); x.drawImage(milkyG, mo, 0);
    x.globalAlpha = c; x.drawImage(milkyC, mo - 2400, 0); x.drawImage(milkyC, mo, 0); x.globalAlpha = 1;
    drawAurora(t, c);
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

    // faint real content behind the active stations
    const st = m._text || (m._text = sceneText(m));
    const annoOn = capOn > .02 || (lastFail && t >= lastFail.t0 && t <= lastFail.t1 + 2.3);
    for (let i = 1; i < 7; i++) {
      const sx = i * GAP + ox; if (sx < -GAP || sx > W + GAP || b.k === 'intro') continue;
      const near = Math.max(0, 1 - Math.abs(p - i) * 1.6), lines = b.k === 'outro' ? null : i === 1 ? st.rules : i === 3 ? st.cobol : i === 4 || i === 5 ? st.python : null;
      if (lines && lines.length) { x.globalAlpha = near * (i === 1 ? .12 : .1) * (annoOn ? 0 : 1); lines.forEach((l, k) => txt(l, sx - 250, 96 + k * 24, 14, 1, 0, 'left', i === 3 || i === 1 ? '232,234,242' : '200,185,255')); x.globalAlpha = 1; }
      if (i === 2 && near > 0) for (let k = 0; k < 30; k++) { const an = k / 30 * 6.283 + t * .3, r = 52 + 16 * Math.sin(k * 1.7 + t); x.fillStyle = `rgba(230,235,250,${.6 * near})`; x.beginPath(); x.arc(sx + Math.cos(an) * r, CY + Math.sin(an) * r * .45, 1, 0, 7); x.fill(); }
    }

    const travelling = b.k !== 'intro' && b.k !== 'swoop' && b.k !== 'outro' && !b.blocked;
    const sy = CY - arc * 100, px = wx + ox;
    filament(ox, t, c, travelling ? px : W / 2, lc);

    // stations
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
      txt(`${STATIONS[i][0]} — ${STATIONS[i][1].toUpperCase()}`, sx, CY + 120, 12, .25 + .6 * near, 3);
      if (b.k !== 'intro' && b.k !== 'swoop') txt(subtitle(m, i, here ? b : {}, u), sx, CY + 140, 11, .15 + .5 * near, 2);
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
    const waiting = mods.map((q, i) => i).filter(i => i > mi || (i === mi && (b.k === 'swoop' || b.k === 'intro')));
    const cpos = i => [dx + CLUSTER[i % CLUSTER.length][0], CY + CLUSTER[i % CLUSTER.length][1]];
    x.setLineDash([2, 5]); x.strokeStyle = `rgba(${lc},.18)`;
    mods.forEach((q, i) => q.depends_on.forEach(d => { const j = mods.findIndex(z => z.id === d); if (j >= 0 && waiting.includes(i) && waiting.includes(j)) { const [a1, a2] = cpos(i), [b1, b2] = cpos(j); x.beginPath(); x.moveTo(a1, a2); x.lineTo(b1, b2); x.stroke(); } }));
    x.setLineDash([]);
    waiting.forEach(i => { const [qx, qy] = cpos(i); const blockedQ = (mods[i].error || '').startsWith('blocked') && i === mi;
      star(qx, qy, t + i, blockedQ ? .3 : .38, '215,222,240', '235,238,248', i);
      if (b.k !== 'intro') txt(mods[i].id.toUpperCase(), qx, qy - 18, 9, .45, 2); });  // names wait until the intro title has faded

    // constellation at Verified: programs already accepted
    const vx = 6 * GAP + ox, vpos = i => [vx + CONST[i % CONST.length][0], CY + CONST[i % CONST.length][1]];
    const verified = mods.map((q, i) => i).filter(i => done(i) && !(i === mi && travelling));
    x.setLineDash([2, 5]); x.strokeStyle = `rgba(${lc},.28)`;
    mods.forEach((q, i) => q.depends_on.forEach(d => { const j = mods.findIndex(z => z.id === d); if (j >= 0 && verified.includes(i) && verified.includes(j)) { const [a1, a2] = vpos(i), [b1, b2] = vpos(j); x.beginPath(); x.moveTo(a1, a2); x.lineTo(b1, b2); x.stroke(); } }));
    x.setLineDash([]);
    verified.forEach(i => { const [qx, qy] = vpos(i); star(qx, qy, t + i, b.k === 'outro' ? .55 : .4, i % 2 ? '120,230,210' : rgb(mix([215, 225, 255], [185, 140, 255], c)), '235,228,255', i); txt(mods[i].id.toUpperCase(), qx, qy - 20, 9, .55, 2); });
    mods.forEach((q, i) => { if (i < mi && q.status !== 'done' && !(q.error || '').startsWith('blocked')) { const fx = 5 * GAP + ox + 40 * (i - mi), fy = CY + 34; star(fx, fy, t, .22, '200,190,200', '220,215,220', i); txt(q.id.toUpperCase() + ' · FAILED', fx, fy + 22, 9, .4, 2); } });

    // the travelling star and its tail
    if (travelling) {
      trail.push([wx, sy]); if (trail.length > 55) trail.shift();
      for (let k = 1; k < trail.length; k++) { const a = k / trail.length, tc = rgb(mix([225, 232, 255], [120, 235, 215], c * (1 - a))); x.strokeStyle = `rgba(${tc},${a * a * .55})`; x.lineWidth = a * 2.4; x.beginPath(); x.moveTo(trail[k - 1][0] + ox, trail[k - 1][1]); x.lineTo(trail[k][0] + ox, trail[k][1]); x.stroke(); }
      const glow = failing ? '255,190,200' : rgb(mix([215, 225, 255], [185, 140, 255], c)), spk = failing ? '255,225,230' : rgb(mix([240, 244, 255], [230, 215, 255], c));
      const ended = b.failedEnd;
      star(px, sy, t, ended ? .55 : b.working ? 1 + .14 * Math.sin(t * 4) : p > 5.98 ? 1.4 : moving ? 1.05 : 1, ended ? '190,185,195' : glow, ended ? '215,210,215' : spk, mi);
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
      txt('LEGACY  →  VERIFIED', W / 2, 70, 20, .9 * a, 10, 'center', '240,240,246', '300');
      txt(`${n} COBOL PROGRAM${n > 1 ? 'S' : ''}  ·  ${R.title.toUpperCase()}`, W / 2, 98, 10, .5 * a, 4);
    }
    if (b.k === 'outro' && !panel.classList.contains('open')) {
      const a = clamp((t - b.t0 - .4) / 1.2), ok = mods.filter(q => q.status === 'done').length;
      const total = mods.reduce((s, q) => s + (q.status === 'done' ? q.tests_total : 0), 0);
      txt(`${ok} / ${n} VERIFIED`, W / 2, H - 78, 20, .9 * a, 8, 'center', '245,246,252', '300');
      txt(`${total} RECORDED OUTPUTS · EVERY ONE MATCHES THE REAL COBOL`, W / 2, H - 54, 10, .55 * a, 3.5);
    }

    if (fr % 3 === 0) grain();
    x.globalAlpha = .06 * (1 - c * .5); x.fillStyle = x.createPattern(grainC, 'repeat'); x.fillRect(0, 0, W, H); x.globalAlpha = 1;
    const vg = x.createRadialGradient(W / 2, H / 2, H * .2, W / 2, H / 2, W * .75);
    vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, `rgba(${rgb(mix([0, 0, 0], [8, 2, 20], c))},.8)`);
    x.fillStyle = vg; x.fillRect(0, 0, W, H);

    // corners
    if (b.k !== 'intro') {
      const left = `${(m.file || m.id).toUpperCase()}  ·  ${String(mi + 1).padStart(2, '0')} / ${String(n).padStart(2, '0')}${m.kind === 'subprogram' ? '  ·  SUBPROGRAM' : ''}`;
      txt(left, 24, 30, 11, .5, 3, 'left');
      const right = b.k === 'outro' ? 'MIGRATION COMPLETE' : b.blocked ? 'BLOCKED' : failing ? 'MISMATCH' : p > 5.98 ? `VERIFIED  ·  ${m.tests_passed} / ${m.tests_total}` : c > .1 ? 'BECOMING PYTHON' : 'LEGACY COBOL';
      // narrow screens: drop the status under the file name instead of letting the two collide
      const fits = measure(left, 11, 3) + measure(right, 11, 3) + 80 < W;
      if (!panel.classList.contains('open')) txt(right, fits ? W - 24 : 24, fits ? 30 : 48, fits ? 11 : 10, fits ? .5 : .4, 3, fits ? 'right' : 'left');
    }
    const label = R.live ? `LIVE  ·  REAL NEMOTRON RUN  ·  ${String(R.codebase || '').toUpperCase()}${R.finished ? '  ·  FINISHED' : ''}`
      : R.kind === 'mutation' ? 'CONTROLLED MUTATION  ·  PLANTED BUG, NOT A MODEL OUTPUT'
      : `REPLAY OF A REAL ${R.mode === 'real_model' ? 'NEMOTRON' : 'OFFLINE FIXTURE'} RUN  ·  ${(R.started_at || '').slice(0, 16).replace('T', ' ')}`;
    if (innerWidth > 1100 && !panel.classList.contains('open')) txt(label, W - 24, H - 22, 9, .32, 2.5, 'right');
    if (travelling && !panel.classList.contains('open') && t < 40) txt('CLICK A STAR OR A RING TO INSPECT', W / 2, H - 48, 9, .22 * clamp((t - 6) / 2) * clamp((40 - t) / 3), 3);
  }

  // ---------- side panel ----------
  const panel = document.getElementById('panel'), pBody = document.getElementById('p-body'), pTabs = document.getElementById('p-tabs');
  let pMod = null, pTab = 'cobol', pStar = null;  // pStar: the module whose star the readout points at
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
  const TABS = [['cobol', 'COBOL'], ['python', 'Python'], ['spec', 'Spec'], ['tests', 'Answer key'], ['attempts', 'Attempts']];
  function hold(worldX) {  // pause the replay while a readout is open; resume on close if it was playing
    if (focusX === null) resumeAfter = playing;
    playing = false; playBtn.textContent = 'Play'; focusX = worldX;
  }
  function openPanel(i, worldX) {
    focus = null; if (worldX !== undefined) hold(worldX);
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
  function openStation(i) {
    const S = window.Stations && window.Stations.get(i + 1);
    const b = beatAt(Math.min(clock, TL.end - 1e-3)), mi = b.mi !== undefined ? b.mi : (b.k === 'outro' ? R.modules.length - 1 : 0);
    const m = R.modules[mi];
    hold(i * GAP); focus = i; pStar = null; capFocus = null;
    document.getElementById('p-title').textContent = `${STATIONS[i][0]} — ${STATIONS[i][1]}`;
    document.getElementById('p-meta').textContent = `${m.file || m.id} · ${m.kind}${S && S.agent ? ' · ' + S.agent : ''}`;
    let out;
    try { out = S ? S.render({ module: m, replay: R, H: window.Stations.H }) : window.Stations.H.empty('No view for this station yet.'); }
    catch (err) { console.error(`station ${i + 1} render:`, err); out = window.Stations.H.empty('This view hit an error. See the console.'); }
    const tabs = out && typeof out === 'object' && Array.isArray(out.tabs) ? out.tabs : null;
    pTabs.style.display = tabs && tabs.length > 1 ? '' : 'none';
    const show = k => { setBody(tabs ? tabs[k].html : String(out || ''));
      [...pTabs.children].forEach((bn, j) => bn.classList.toggle('on', j === k)); };
    pTabs.innerHTML = tabs ? tabs.map((tb, j) => `<button data-st="${j}">${esc(tb.label)}</button>`).join('') : '';
    pTabs.onclick = e => { const k = e.target.dataset && e.target.dataset.st; if (k !== undefined) show(+k); };
    show(0); panel.classList.add('open', 'station'); panel.setAttribute('aria-hidden', 'false');
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
    const hh = hitAt(e); if (!hh) { closeCaption(); return closePanel(); }
    if (typeof hh.id === 'string' && hh.id.startsWith('det:')) openStation(+hh.id.slice(4));
    else if (typeof hh.id === 'string') openCaption(+hh.id.slice(3));
    else openPanel(hh.id, hh.x - (W / 2 - cam));  // the star's world position, so the camera can frame it
  });
  cv.addEventListener('mousemove', e => cv.classList.toggle('pointer', !!hitAt(e)));

  // ---------- loading: recordings, the intake, live runs ----------
  const sel = document.getElementById('replay'), intake = document.getElementById('intake');
  const fallbackBtn = document.getElementById('fallback'), backBtn = document.getElementById('backlive');
  let API = null, pollTimer = null, liveSession = null, recordings = [];
  function intakeOpen() { return intake.classList.contains('open'); }
  function normalize(rep) { (rep.modules || []).forEach(q => { q.depends_on = q.depends_on || []; q.history = q.history || []; }); return rep; }
  function stopLive() { clearTimeout(pollTimer); pollTimer = null; liveSession = null; fallbackBtn.hidden = true; }
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
  async function load(name) {
    stopLive(); const lv = sel.querySelector('option[value="__live"]'); if (lv) lv.remove();
    const res = await fetch(`replays/${name}.json`, { cache: 'no-store' }); if (!res.ok) throw new Error(`replay ${name}: ${res.status}`);
    R = normalize(await res.json());
    TL = buildTimeline(R); restart(); closePanel(); closeCaption(); lastFail = null; playing = true; playBtn.textContent = 'Pause';
    document.getElementById('loading').style.display = 'none'; closeIntake();
    if ([...sel.options].some(o => o.value === name)) sel.value = name;
    history.replaceState(null, '', `#${name}`);
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
    pollTimer = setTimeout(poll, 1500);
  }
  async function startLive(codebase, recording) {
    note('Starting a real Nemotron run…');
    let r;
    try { r = await fetch('api/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ codebase }) }); }
    catch (err) { return note('The local server is not reachable.', true); }
    const body = await r.json().catch(() => ({}));
    if (!r.ok) {
      note(body.error || 'The run could not start.', true);
      if (recording) setTimeout(() => load(recording).catch(showError), 1600);
      return;
    }
    attach(body.session);
  }
  // follow a run (started here, or from the terminal: open the page at #live=<session>)
  function attach(session) {
    stopLive(); liveSession = session; backBtn.hidden = true;
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
  function openIntake() { playing = false; playBtn.textContent = 'Play'; closePanel(); closeCaption(); intake.classList.add('open'); intake.setAttribute('aria-hidden', 'false'); document.body.classList.add('intake-on'); renderIntake(); }
  function closeIntake() { intake.classList.remove('open'); intake.setAttribute('aria-hidden', 'true'); document.body.classList.remove('intake-on'); note(''); }
  document.getElementById('intake-btn').onclick = openIntake;
  async function renderIntake() {
    const list = document.getElementById('in-list'), live = !!(API && API.live);
    let items = [];
    if (API) {
      try { items = (await (await fetch('api/codebases', { cache: 'no-store' })).json()).codebases || []; } catch (err) { items = []; }
    }
    const running = await runningSession();
    if (running) items.unshift({ name: 'Live run in progress', about: 'A real Nemotron run is going right now. Watch where it is.', session: running });
    const recorded = new Set(items.map(c => c.recording).filter(Boolean));
    recordings.filter(r => !recorded.has(r.name)).forEach(r => items.push({ name: r.title, about: r.kind === 'mutation' ? 'A one-cent rounding bug planted in a verified rewrite, to show the check catches it.' : '', recording: r.name }));
    list.innerHTML = items.map((c, i) => `<div class="cb"><div class="cb-name">${esc(c.name)}</div>` +
      (c.session ? '<div class="cb-meta">live now</div>' : c.programs ? `<div class="cb-meta">${c.programs} program${c.programs === 1 ? '' : 's'}${c.copybooks ? ` · ${c.copybooks} cop${c.copybooks === 1 ? 'ybook' : 'ybooks'}` : ''}${c.uploaded ? ' · uploaded' : ''}</div>` : '<div class="cb-meta">recording</div>') +
      (c.about ? `<div class="cb-about">${esc(c.about)}</div>` : '') +
      `<div class="cb-act">${c.session ? `<button class="live" data-i="${i}" data-a="watch">Watch live</button>` : ''}${c.codebase ? `<button class="live" data-i="${i}" data-a="live" ${live ? '' : 'disabled title="Live runs need the local server and an NVIDIA API key"'}>Run live</button>` : ''}` +
      `${c.recording ? `<button data-i="${i}" data-a="rec">Watch recording</button>` : ''}</div></div>`).join('');
    list.onclick = e => {
      const bn = e.target.closest('button'); if (!bn || bn.disabled) return;
      const c = items[+bn.dataset.i];
      if (bn.dataset.a === 'watch') attach(c.session);
      else if (bn.dataset.a === 'live') startLive(c.codebase, c.recording);
      else load(c.recording).catch(showError);
    };
    document.getElementById('drop').style.display = API ? '' : 'none';
    document.getElementById('in-foot').textContent = !API ? 'Recordings only. For live runs: python tools/serve.py'
      : live ? 'Live runs use real NVIDIA Nemotron calls and take a few minutes' : 'Live runs need NVIDIA_API_KEY in .env';
  }
  const drop = document.getElementById('drop'), dropFile = document.getElementById('drop-file');
  async function upload(file) {
    if (!file) return;
    if (!/\.zip$/i.test(file.name)) return note('Drop a .zip of COBOL files (.cbl, .cob, .cpy).', true);
    if (!(API && API.live)) return note('Live runs need the local server and an NVIDIA API key.', true);
    note(`Reading ${file.name}…`);
    const r = await fetch('api/upload', { method: 'POST', headers: { 'Content-Type': 'application/zip', 'X-Filename': file.name }, body: file }).catch(() => null);
    const body = r ? await r.json().catch(() => ({})) : {};
    if (!r || !r.ok) return note(body.error || 'Upload failed.', true);
    note(`${body.files} COBOL files found. Starting…`);
    startLive(body.codebase, null);
  }
  dropFile.onchange = () => upload(dropFile.files[0]);
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
    openIntake();
  })().catch(showError);
  requestAnimationFrame(frame);
  // for rehearsing a moment: galaxy.seek(seconds), galaxy.t
  window.galaxy = { seek(s) { clock = Math.max(0, s); trail = []; lastFail = null; cam = (beatAt(clock).k === 'move' ? beatAt(clock).a : (beatAt(clock).at || 0)) * GAP;
                             for (let i = 0; i < 90; i++) { x.setTransform(DPR * K, 0, 0, DPR * K, 0, 0); x.save(); draw(clock); x.restore(); } }, get t() { return clock; },
                    get beats() { return TL && TL.beats.map(b => [b.k, b.mi, b.at, +b.t0.toFixed(1), b.fail || false]); },
                    get hits() { return hits.map(h => ({ id: h.id, x: h.x * K, y: h.y * K })); } };  // css px, for rehearsal checks
})();
