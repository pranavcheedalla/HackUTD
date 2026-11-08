"""Module id: interest

Python 3.11 port of COBOL program INTEREST.
Byte-for-byte equivalent DISPLAY output for every input.
"""
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import re


# ---------------------------------------------------------------------------
# COBOL data semantics helpers (copied verbatim per migration standard)
# ---------------------------------------------------------------------------

def pic_store(value, int_digits, dec_digits=0, signed=False, rounded=False):
    """Store a value into PIC [S]9(int_digits)V9(dec_digits), like COBOL MOVE/COMPUTE.

    - extra decimals are TRUNCATED (unless the COBOL statement says ROUNDED)
    - extra high-order integer digits are silently dropped (no ON SIZE ERROR)
    - unsigned fields drop the sign
    """
    q = Decimal(1).scaleb(-dec_digits)
    v = Decimal(value).quantize(q, rounding=ROUND_HALF_UP if rounded else ROUND_DOWN)
    negative = v < 0
    v = (abs(v) % (Decimal(10) ** int_digits)).quantize(q)
    return -v if (negative and signed) else v


def pic_from_text(text, int_digits, dec_digits=0, signed=False):
    """Parse raw characters of a PIC 9 field read by ACCEPT (implied decimal point).
    '0012345' with dec_digits=2 -> Decimal('123.45'). Spaces count as zeros."""
    s = text.strip()
    negative = s.startswith("-") or s.endswith("-")
    digits = re.sub(r"[^0-9]", "", text.replace(" ", "0")) or "0"
    v = Decimal(int(digits)).scaleb(-dec_digits)
    return pic_store(-v if negative else v, int_digits, dec_digits, signed)


def split_fixed(line, widths):
    """Split an ACCEPTed line into fixed-width fields (group item layout).
    Short lines are padded with spaces, long lines are cut, like COBOL."""
    total = sum(widths)
    line = line[:total].ljust(total)
    out, pos = [], 0
    for w in widths:
        out.append(line[pos : pos + w])
        pos += w
    return out


def display_num(value, int_digits, dec_digits=0, signed=False):
    """How GnuCOBOL DISPLAYs an un-edited numeric field PIC [S]9(n)V9(m):
    leading zeros, '.' for the implied decimal, leading +/- if signed.
    e.g. PIC 9(3)V99 1.5 -> '001.50';  PIC S9(3) -7 -> '-007'."""
    v = pic_store(value, int_digits, dec_digits, signed)
    a = abs(v)
    int_part = int(a)
    s = str(int_part).zfill(int_digits)
    if dec_digits:
        frac = int((a - int_part).scaleb(dec_digits))
        s += "." + str(frac).zfill(dec_digits)
    if signed:
        s = ("-" if v < 0 else "+") + s
    return s


def _expand_pic(pic):
    return re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic.upper())


def edit_picture(value, pic):
    """Format a value with a numeric-EDITED picture, e.g. 'Z,ZZZ,ZZ9.99', '-ZZ9.99',
    'ZZ9.99CR', '$ZZ,ZZ9.99', '9(5)'. Supports Z 9 , . + - CR DB and one fixed $.
    Truncates extra decimals and high-order digits exactly like a COBOL MOVE."""
    p = _expand_pic(pic)
    lead_sign = p[0] if p[:1] in "+-" else ""
    if lead_sign:
        p = p[1:]
    trail_sign = ""
    for t in ("CR", "DB", "+", "-"):
        if p.endswith(t):
            trail_sign, p = t, p[: -len(t)]
            break
    dollar = p.startswith("$")
    if dollar:
        p = p[1:]

    int_pat, _, dec_pat = p.partition(".")
    n_int = sum(c in "9Z" for c in int_pat)
    n_dec = sum(c in "9Z" for c in dec_pat)
    v = pic_store(value, n_int, n_dec, signed=True)
    negative = v < 0
    a = abs(v)
    int_digits = str(int(a)).zfill(n_int)
    dec_digits = str(int((a - int(a)).scaleb(n_dec))).zfill(n_dec) if n_dec else ""

    # integer part with zero suppression
    out, di, suppressing = [], 0, True
    for c in int_pat:
        if c in "9Z":
            d = int_digits[di]
            di += 1
            if c == "Z" and suppressing and d == "0":
                out.append(" ")
            else:
                suppressing = False
                out.append(d)
        elif c == ",":
            out.append(" " if suppressing else ",")
        else:
            out.append(c)
    body = "".join(out)

    if "9" not in p and a == 0:  # all-Z picture with zero value -> all blanks
        return " " * len(_expand_pic(pic))
    if dec_pat:
        body += "." + dec_digits

    if dollar:
        body = "$" + body
    if lead_sign:
        body = ("-" if negative else ("+" if lead_sign == "+" else " ")) + body
    if trail_sign in ("+", "-"):
        body += "-" if negative else ("+" if trail_sign == "+" else " ")
    elif trail_sign:
        body += trail_sign if negative else "  "
    return body


# ---------------------------------------------------------------------------
# Working-storage fields mirroring the COBOL layout
# ---------------------------------------------------------------------------

class WorkingStorage:
    """Holds all WORKING-STORAGE items for program INTEREST."""

    def __init__(self) -> None:
        # WS-INPUT group (fixed-width ACCEPT)
        self.in_principal = Decimal("0")   # PIC 9(7)V99
        self.in_rate = Decimal("0")        # PIC 9(2)V99
        self.in_years = Decimal("0")       # PIC 9(2)

        # Computed fields
        self.ws_interest = Decimal("0")    # PIC 9(7)V99
        self.ws_total = Decimal("0")       # PIC 9(8)V99

        # Edited output fields (alphanumeric DISPLAY images)
        self.out_interest = " " * 10       # PIC Z(6)9.99
        self.out_total = " " * 11          # PIC Z(7)9.99


# ---------------------------------------------------------------------------
# Paragraph implementations
# ---------------------------------------------------------------------------

def main_para(ws: WorkingStorage, input_line: str) -> str:
    """MAIN-PARA logic translated to Python.

    Returns everything the COBOL program would DISPLAY, lines joined by "\n",
    with NO trailing newline.
    """
    lines = []

    # ACCEPT WS-INPUT  (fixed-width split: 9 + 4 + 2 = 15 chars)
    # Short input padded with spaces; long input truncated.
    principal_text, rate_text, years_text = split_fixed(input_line, [9, 4, 2])

    # PIC 9(7)V99 fields: implied decimal point, spaces count as zeros
    ws.in_principal = pic_from_text(principal_text, 7, 2)
    ws.in_rate = pic_from_text(rate_text, 2, 2)
    ws.in_years = pic_from_text(years_text, 2, 0)

    # IF IN-YEARS = 0  -> error branch, STOP RUN (no arithmetic)
    if ws.in_years == 0:
        lines.append("ERROR: YEARS MUST BE AT LEAST 1")
        return "\n".join(lines)

    # COMPUTE WS-INTEREST ROUNDED = IN-PRINCIPAL * IN-RATE * IN-YEARS / 100
    # Intermediate expression keeps full precision; ROUNDED applies only at store.
    exact_interest = ws.in_principal * ws.in_rate * ws.in_years / Decimal(100)
    ws.ws_interest = pic_store(exact_interest, 7, 2, signed=False, rounded=True)

    # COMPUTE WS-TOTAL = IN-PRINCIPAL + WS-INTEREST
    # No ROUNDED -> truncation at store; no ON SIZE ERROR -> silent high-order drop.
    ws.ws_total = pic_store(ws.in_principal + ws.ws_interest, 8, 2, signed=False)

    # MOVE WS-INTEREST TO OUT-INTEREST  (PIC Z(6)9.99)
    ws.out_interest = edit_picture(ws.ws_interest, "Z(6)9.99")

    # MOVE WS-TOTAL TO OUT-TOTAL  (PIC Z(7)9.99)
    ws.out_total = edit_picture(ws.ws_total, "Z(7)9.99")

    # DISPLAY "INTEREST: " OUT-INTEREST   (concatenation, no separator)
    lines.append("INTEREST: " + ws.out_interest)

    # DISPLAY "TOTAL:    " OUT-TOTAL      (literal has exactly 5 trailing spaces)
    lines.append("TOTAL:    " + ws.out_total)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point required by the migration harness
# ---------------------------------------------------------------------------

def main(input_line: str) -> str:
    """Entry point: emulate one run of COBOL program INTEREST.

    Never raises. Returns DISPLAY output with lines joined by "\n",
    no trailing newline.
    """
    ws = WorkingStorage()
    return main_para(ws, input_line)


# ---------------------------------------------------------------------------
# Allow direct execution: python interest.py < input.txt
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    data = sys.stdin.read()
    # COBOL ACCEPT reads exactly one line; strip only the trailing newline
    # that the terminal adds, not spaces that are part of the record.
    line = data.rstrip("\n")
    print(main(line), end="")
