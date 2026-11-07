"""COBOL data semantics in plain Python.

This file's source is shown to the rewrite model and is INLINED into any
generated module that uses these helpers, so every file in modern/ is standalone.
Keep it dependency-free (stdlib `decimal` only).
"""
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import re


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


HELPER_NAMES = ("pic_store", "pic_from_text", "split_fixed", "display_num", "edit_picture")
