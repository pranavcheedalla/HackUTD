"""Module: invoice

Python 3.11 migration of COBOL program INVOICE.
Byte-for-byte equivalent DISPLAY output for every input.
"""

from decimal import Decimal
import discount


# ---------------------------------------------------------------------------
# COBOL data semantics helpers (copied verbatim per migration rules)
# ---------------------------------------------------------------------------

def pic_store(value, int_digits, dec_digits=0, signed=False, rounded=False):
    """Store a value into PIC [S]9(int_digits)V9(dec_digits), like COBOL MOVE/COMPUTE.

    - extra decimals are TRUNCATED (unless the COBOL statement says ROUNDED)
    - extra high-order integer digits are silently dropped (no ON SIZE ERROR)
    - unsigned fields drop the sign
    """
    from decimal import ROUND_DOWN, ROUND_HALF_UP
    q = Decimal(1).scaleb(-dec_digits)
    v = Decimal(value).quantize(q, rounding=ROUND_HALF_UP if rounded else ROUND_DOWN)
    negative = v < 0
    v = (abs(v) % (Decimal(10) ** int_digits)).quantize(q)
    return -v if (negative and signed) else v


def pic_from_text(text, int_digits, dec_digits=0, signed=False):
    """Parse raw characters of a PIC 9 field read by ACCEPT (implied decimal point).
    '0012345' with dec_digits=2 -> Decimal('123.45'). Spaces count as zeros."""
    import re
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
    import re
    return re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic.upper())


def edit_picture(value, pic):
    """Format a value with a numeric-EDITED picture, e.g. 'Z,ZZZ,ZZ9.99', '-ZZ9.99',
    'ZZ9.99CR', '$ZZ,ZZ9.99', '9(5)'. Supports Z 9 , . + - CR DB and one fixed $.
    Truncates extra decimals and high-order digits exactly like a COBOL MOVE."""
    import re
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
# Working-storage fields (mirror COBOL 01-level items)
# ---------------------------------------------------------------------------

# INV-RECORD group (12 chars total)
#   INV-QTY        PIC 9(4)        cols 1-4
#   INV-UNIT-PRICE PIC 9(5)V99     cols 5-11  (7 digits, implied 2 decimals)
#   INV-CUST-TIER  PIC X           col 12
INV_QTY_INT = 4
INV_QTY_DEC = 0
INV_PRICE_INT = 5
INV_PRICE_DEC = 2
INV_TIER_LEN = 1

# WS-SUBTOTAL      PIC 9(7)V99
WS_SUBTOTAL_INT = 7
WS_SUBTOTAL_DEC = 2

# WS-DISC-RATE     PIC 9(2)V99
WS_DISC_RATE_INT = 2
WS_DISC_RATE_DEC = 2

# WS-DISC-AMT      PIC 9(5)V99   (no ON SIZE ERROR)
WS_DISC_AMT_INT = 5
WS_DISC_AMT_DEC = 2

# WS-NET           PIC S9(7)V99  (no ON SIZE ERROR)
WS_NET_INT = 7
WS_NET_DEC = 2
WS_NET_SIGNED = True

# OUT-SUBTOTAL     PIC Z(6)9.99   -> expanded "ZZZZZZ9.99" (10 chars)
# OUT-DISC         PIC Z(4)9.99   -> expanded "ZZZZ9.99"   (8 chars)
# OUT-NET          PIC -Z(6)9.99  -> expanded "-ZZZZZZ9.99" (11 chars)


def main(input_line: str) -> str:
    """Return everything the COBOL program would print, lines joined by "\n",
    no trailing newline. Never raises."""
    lines = []

    # ---- ACCEPT INV-RECORD -------------------------------------------------
    # Fixed-width split: 4 + 7 + 1 = 12 characters. Short line padded with
    # spaces; long line truncated.
    qty_text, price_text, tier_text = split_fixed(input_line, [4, 7, 1])

    # PIC 9 fields read by ACCEPT: implied decimal point, spaces count as zeros.
    inv_qty = pic_from_text(qty_text, INV_QTY_INT, INV_QTY_DEC, signed=False)
    inv_unit_price = pic_from_text(
        price_text, INV_PRICE_INT, INV_PRICE_DEC, signed=False
    )
    inv_cust_tier = tier_text  # PIC X, kept as-is (1 char)

    # ---- IF INV-QTY = ZERO -------------------------------------------------
    if inv_qty == Decimal("0"):
        lines.append("ERROR: QUANTITY MUST BE AT LEAST 1")
        return "\n".join(lines)

    # ---- COMPUTE WS-SUBTOTAL = INV-QTY * INV-UNIT-PRICE (ON SIZE ERROR) ----
    # Intermediate result keeps full precision; truncation/capacity check only
    # when stored into PIC 9(7)V99.
    subtotal_full = inv_qty * inv_unit_price
    max_subtotal = Decimal(10) ** WS_SUBTOTAL_INT  # 10^7 = 10000000.00 capacity
    if subtotal_full >= max_subtotal:
        # Integer part needs more than 7 digits -> ON SIZE ERROR branch.
        lines.append("ERROR: SUBTOTAL TOO LARGE")
        return "\n".join(lines)
    ws_subtotal = pic_store(
        subtotal_full, WS_SUBTOTAL_INT, WS_SUBTOTAL_DEC, signed=False
    )

    # ---- CALL 'DISCOUNT' USING INV-CUST-TIER WS-SUBTOTAL WS-DISC-RATE ------
    # COBOL passes BY REFERENCE; callee may modify any argument. Unpack the
    # returned tuple back into the caller's variables. The caller then stores
    # ws_subtotal / ws_disc_rate again per its own PIC (they already fit).
    tier, ws_subtotal, ws_disc_rate = discount.call(
        inv_cust_tier, ws_subtotal, Decimal("0")
    )
    # Re-store per caller PICs (no-op here since they already fit, but keeps
    # semantics exact if the callee had produced out-of-range values).
    ws_subtotal = pic_store(ws_subtotal, WS_SUBTOTAL_INT, WS_SUBTOTAL_DEC, signed=False)
    ws_disc_rate = pic_store(
        ws_disc_rate, WS_DISC_RATE_INT, WS_DISC_RATE_DEC, signed=False
    )

    # ---- COMPUTE WS-DISC-AMT = WS-SUBTOTAL * WS-DISC-RATE / 100 ------------
    # Exact intermediate decimal arithmetic; truncation to 2 decimals occurs
    # only when stored into PIC 9(5)V99. No ON SIZE ERROR -> overflow silently
    # loses high-order digits.
    disc_amt_full = ws_subtotal * ws_disc_rate / Decimal("100")
    ws_disc_amt = pic_store(
        disc_amt_full, WS_DISC_AMT_INT, WS_DISC_AMT_DEC, signed=False
    )

    # ---- COMPUTE WS-NET = WS-SUBTOTAL - WS-DISC-AMT ------------------------
    # Exact intermediate arithmetic; no ON SIZE ERROR -> overflow above
    # PIC S9(7)V99 silently loses high-order digits.
    ws_net_full = ws_subtotal - ws_disc_amt
    ws_net = pic_store(
        ws_net_full, WS_NET_INT, WS_NET_DEC, signed=WS_NET_SIGNED
    )

    # ---- MOVE to edited output fields --------------------------------------
    out_subtotal = edit_picture(ws_subtotal, "Z(6)9.99")
    out_disc = edit_picture(ws_disc_amt, "Z(4)9.99")
    out_net = edit_picture(ws_net, "-Z(6)9.99")

    # ---- DISPLAY lines ------------------------------------------------------
    # Each DISPLAY statement is one line; items concatenate with NO separator.
    lines.append("SUBTOTAL: " + out_subtotal)
    lines.append("DISCOUNT: " + out_disc)
    lines.append("NET:     " + out_net)

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    line = sys.stdin.readline().rstrip("\n")
    print(main(line), end="")
