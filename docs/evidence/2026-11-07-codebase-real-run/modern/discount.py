"""Migration of COBOL subprogram DISCOUNT to Python 3.11.

Picks a discount rate (percent) based on customer tier, subtotal threshold,
or defaults to zero. The chosen rate is moved into LK-RATE and returned.

This is a SUBPROGRAM (PROCEDURE DIVISION USING ...): it never ACCEPTs input
or DISPLAYs output itself. Its result is the value of its LINKAGE parameters
after it runs (COBOL passes them BY REFERENCE).

Two entry points are provided:
    call(lk_tier, lk_subtotal, lk_rate) -> tuple
    main(input_line: str) -> str
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
# Linkage record for DISCOUNT
# ---------------------------------------------------------------------------

class DiscountLinkage:
    """Holds the LINKAGE SECTION fields of DISCOUNT between calls."""

    def __init__(self):
        # LK-TIER: PIC X (1 char, alphanumeric)
        self.lk_tier = " "
        # LK-SUBTOTAL: PIC 9(7)V99 (unsigned, 7 int digits + 2 implied decimals)
        self.lk_subtotal = Decimal("0")
        # LK-RATE: PIC 9(2)V99 (unsigned, 2 int digits + 2 implied decimals)
        self.lk_rate = Decimal("0")


# ---------------------------------------------------------------------------
# Subprogram entry point: call()
# ---------------------------------------------------------------------------

def call(lk_tier, lk_subtotal, lk_rate):
    """Execute DISCOUNT logic with the given linkage parameters.

    Parameters (USING order):
        lk_tier: str   (PIC X)
        lk_subtotal: Decimal (PIC 9(7)V99)
        lk_rate: Decimal (PIC 9(2)V99)

    Returns a tuple of every parameter after the call, in the same order,
    each value already stored per its PIC (truncated, fixed length for text).
    """
    # Store inputs into their PIC fields (truncation applied at store time).
    # LK-TIER is PIC X(1): cut/pad to exactly 1 character.
    tier = str(lk_tier)[:1].ljust(1)
    # LK-SUBTOTAL is PIC 9(7)V99 unsigned: truncate decimals, drop high-order digits,
    # and drop any sign (unsigned field loses the minus sign).
    subtotal = pic_store(lk_subtotal, 7, 2, signed=False)
    # LK-RATE is PIC 9(2)V99 unsigned: same treatment.
    rate = pic_store(lk_rate, 2, 2, signed=False)

    # PROCEDURE DIVISION: EVALUATE TRUE
    # COBOL evaluates WHEN clauses in order; first match wins.
    if tier == "G":
        # MOVE 12.50 TO LK-RATE  (no ROUNDED; literal fits exactly)
        rate = pic_store(Decimal("12.50"), 2, 2, signed=False)
    elif tier == "S":
        # MOVE 7.25 TO LK-RATE
        rate = pic_store(Decimal("7.25"), 2, 2, signed=False)
    elif subtotal >= Decimal("1000.00"):
        # Comparison uses the full 9(7)V99 implied-decimal value.
        # MOVE 5.00 TO LK-RATE
        rate = pic_store(Decimal("5.00"), 2, 2, signed=False)
    else:
        # WHEN OTHER: MOVE 0 TO LK-RATE
        rate = pic_store(Decimal("0"), 2, 2, signed=False)

    return (tier, subtotal, rate)


# ---------------------------------------------------------------------------
# Test-driver entry point: main()
# ---------------------------------------------------------------------------

def main(input_line: str) -> str:
    """Parse a '|'-joined input line, run call(), and return result line.

    Input format: LK-TIER|LK-SUBTOTAL|LK-RATE
    Numbers are decimal text (e.g. "G|100.00|0").
    Output format: LK-TIER=value|LK-SUBTOTAL=value|LK-RATE=value
    Numeric values are zero-padded as 9(int).9(dec); text values exactly as stored.
    """
    # Split on literal '|' delimiter (COBOL UNSTRING ... DELIMITED BY '|' equivalent).
    parts = input_line.split("|")

    # Pad missing fields with empty strings (short input).
    while len(parts) < 3:
        parts.append("")

    # LK-TIER: PIC X(1), text taken as-is (cut/padded to length 1 inside call()).
    lk_tier = parts[0]

    # LK-SUBTOTAL: parse like FUNCTION NUMVAL (human-readable number), then store into PIC 9(7)V99.
    try:
        lk_subtotal_raw = Decimal(parts[1])
    except Exception:
        # Malformed numeric input: COBOL would not crash; treat as zero per NUMVAL leniency.
        # NUMVAL on invalid data returns 0 in GnuCOBOL default behavior.
        lk_subtotal_raw = Decimal("0")

    # LK-RATE: parse like FUNCTION NUMVAL, then store into PIC 9(2)V99.
    try:
        lk_rate_raw = Decimal(parts[2])
    except Exception:
        lk_rate_raw = Decimal("0")

    # Execute the subprogram.
    out_tier, out_subtotal, out_rate = call(lk_tier, lk_subtotal_raw, lk_rate_raw)

    # Format output: NAME=value|NAME=value|...
    # LK-TIER: exactly as stored (1 char).
    tier_str = out_tier
    # LK-SUBTOTAL: PIC 9(7)V99 unsigned -> "0000100.00" style.
    subtotal_str = display_num(out_subtotal, 7, 2, signed=False)
    # LK-RATE: PIC 9(2)V99 unsigned -> "12.50" style (zero-padded to 2 int digits).
    rate_str = display_num(out_rate, 2, 2, signed=False)

    return f"LK-TIER={tier_str}|LK-SUBTOTAL={subtotal_str}|LK-RATE={rate_str}"


# ---------------------------------------------------------------------------
# Allow direct execution: read one line from stdin, print result.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    line = sys.stdin.readline()
    # Strip only the trailing newline; keep everything else as the input line.
    if line.endswith("\n"):
        line = line[:-1]
    print(main(line), end="")
