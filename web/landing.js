// The landing page's legacy terminal: an excerpt of the bank codebase's COBOL (samples/bank/loanpay.cbl)
// typing out at the edge of the sky. When the program ends, the old screen breaks up and starts over.
(() => {
  const el = document.getElementById('crt'), intake = document.getElementById('intake');
  if (!el || !intake) return;
  const HEAD = 'RETAIL BANK  ·  LOANPAY.CBL';
  const LINES = [
    '       IDENTIFICATION DIVISION.',
    '       PROGRAM-ID. LOANPAY.',
    '       DATA DIVISION.',
    '       WORKING-STORAGE SECTION.',
    '       01  WS-INPUT.',
    '           05  IN-PRINCIPAL  PIC 9(7)V99.',
    '           05  IN-RATE       PIC 9(2)V99.',
    '           05  IN-MONTHS     PIC 9(3).',
    '       PROCEDURE DIVISION.',
    '           ACCEPT WS-INPUT',
    '           COMPUTE WS-INTEREST ROUNDED =',
    '               IN-PRINCIPAL * IN-RATE',
    '               * IN-MONTHS / 1200',
    '           COMPUTE WS-PAYMENT =',
    '               WS-TOTAL / IN-MONTHS',
    '           DISPLAY "PAYMENT: " OUT-PAYMENT',
    '           STOP RUN.',
  ].map(l => l.slice(7));  // the sequence-number columns add nothing at this size
  const KEEP = 12;
  const render = (lines, cursor) => {
    el.textContent = '';
    const h = document.createElement('span'); h.className = 'crt-h'; h.textContent = HEAD; el.appendChild(h);
    el.appendChild(document.createTextNode(lines.slice(-KEEP).join('\n')));
    if (cursor) { const c = document.createElement('span'); c.className = 'crt-cur'; el.appendChild(c); }
  };
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) { render(LINES, false); return; }

  let line = 0, ch = 0, shown = [];
  function tick() {
    if (!intake.classList.contains('open')) return setTimeout(tick, 500);  // idle behind the galaxy
    if (line >= LINES.length) {  // the program ends: the screen breaks up, then it starts over
      el.classList.remove('glitch'); void el.offsetWidth; el.classList.add('glitch');
      return setTimeout(() => { line = 0; ch = 0; shown = []; render(shown, true); setTimeout(tick, 900); }, 2600);
    }
    const text = LINES[line];
    ch++;
    shown[line] = text.slice(0, ch);
    render(shown, true);
    if (ch >= text.length) { line++; ch = 0; return setTimeout(tick, 260 + Math.random() * 380); }
    setTimeout(tick, 22 + Math.random() * 40);
  }
  render(shown, true);
  setTimeout(tick, 1200);
})();
