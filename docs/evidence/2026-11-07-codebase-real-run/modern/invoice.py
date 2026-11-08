"""Migration of COBOL program INVOICE to Python 3.11.

Reads one fixed-width 12-character line (quantity, unit price, customer tier),
computes subtotal and discount via the DISCOUNT subprogram, and displays
formatted output or error messages.

Output is byte-for-byte identical to the COBOL DISPLAY output.
"""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import re

import discount


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
# Working-storage record for INVOICE
# ---------------------------------------------------------------------------

class InvoiceRecord:
    """Holds the WORKING-STORAGE fields of INVOICE between paragraphs."""

    def __init__(self):
        # INV-QTY: PIC 9(4) unsigned 4-digit integer
        self.inv_qty = Decimal("0")
        # INV-UNIT-PRICE: PIC 9(5)V99 unsigned
        self.inv_unit_price = Decimal("0")
        # INV-CUST-TIER: PIC X (1 char)
        self.inv_cust_tier = " "
        # WS-SUBTOTAL: PIC 9(7)V99 unsigned
        self.ws_subtotal = Decimal("0")
        # WS-DISC-RATE: PIC 9(2)V99 unsigned
        self.ws_disc_rate = Decimal("0")
        # WS-DISC-AMT: PIC 9(5)V99 unsigned
        self.ws_disc_amt = Decimal("0")
        # WS-NET: PIC S9(7)V99 signed
        self.ws_net = Decimal("0")
        # OUT-SUBTOTAL: PIC Z(6)9.99 edited
        self.out_subtotal = ""
        # OUT-DISC: PIC Z(4)9.99 edited
        self.out_disc = ""
        # OUT-NET: PIC -Z(6)9.99 edited
        self.out_net = ""


# ---------------------------------------------------------------------------
# Paragraph: MAIN-PARA
# ---------------------------------------------------------------------------

def main_para(rec: InvoiceRecord, input_line: str) -> str:
    """Execute MAIN-PARA logic. Returns the full DISPLAY output (lines joined by \n)."""
    output_lines = []

    # ACCEPT INV-RECORD  -> fixed-width split: 4 + 7 + 1 = 12 chars
    # Short line padded with spaces; long line cut.
    qty_text, price_text, tier_text = split_fixed(input_line, [4, 7, 1])

    # INV-QTY: PIC 9(4) unsigned integer (dec_digits=0). Spaces count as zeros.
    rec.inv_qty = pic_from_text(qty_text, 4, 0, signed=False)
    # INV-UNIT-PRICE: PIC 9(5)V99 unsigned (implied decimal point, no point stored).
    rec.inv_unit_price = pic_from_text(price_text, 5, 2, signed=False)
    # INV-CUST-TIER: PIC X(1) text taken as-is (cut/padded to length 1 inside call()).
    rec.inv_cust_tier = tier_text

    # IF INV-QTY = ZERO
    if rec.inv_qty == Decimal("0"):
        output_lines.append("ERROR: QUANTITY MUST BE AT LEAST 1")
        return "\n".join(output_lines)

    # COMPUTE WS-SUBTOTAL = INV-QTY * INV-UNIT-PRICE
    #   ON SIZE ERROR DISPLAY "ERROR: SUBTOTAL TOO LARGE" STOP RUN
    # Intermediate result keeps full precision; size error checks integer digits vs 7.
    subtotal_full = rec.inv_qty * rec.inv_unit_price
    if int(subtotal_full) >= Decimal(10) ** 7:
        output_lines.append("ERROR: SUBTOTAL TOO LARGE")
        return "\n".join(output_lines)
    # No size error: store with truncation into PIC 9(7)V99
    rec.ws_subtotal = pic_store(subtotal_full, 7, 2, signed=False)

    # CALL 'DISCOUNT' USING INV-CUST-TIER WS-SUBTOTAL WS-DISC-RATE
    # COBOL passes BY REFERENCE; callee may change any argument.
    tier, subtotal_after_call, rate = discount.call(
        rec.inv_cust_tier, rec.ws_subtotal, rec.ws_disc_rate
    )
    rec.inv_cust_tier = tier
    rec.ws_subtotal = subtotal_after_call
    rec.ws_disc_rate = rate

    # COMPUTE WS-DISC-AMT = WS-SUBTOTAL * WS-DISC-RATE / 100
    # Full precision intermediate; truncate to 2 decimals when stored in PIC 9(5)V99.
    # High-order digits silently lost if > 99999.99.
    disc_amt_full = rec.ws_subtotal * rec.ws_disc_rate / Decimal("100")
    rec.ws_disc_amt = pic_store(disc_amt_full, 5, 2, signed=False)

    # COMPUTE WS-NET = WS-SUBTOTAL - WS-DISC-AMT
    # High-order digits silently lost if > 9999999.99 (signed field).
    net_full = rec.ws_subtotal - rec.ws_disc_amt
    rec.ws_net = pic_store(net_full, 7, 2, signed=True)

    # MOVE WS-SUBTOTAL TO OUT-SUBTOTAL  (PIC Z(6)9.99)
    rec.out_subtotal = edit_picture(rec.ws_subtotal, "Z(6)9.99")
    # MOVE WS-DISC-AMT TO OUT-DISC  (PIC Z(4)9.99)
    rec.out_disc = edit_picture(rec.ws_disc_amt, "Z(4)9.99")
    # MOVE WS-NET TO OUT-NET  (PIC -Z(6)9.99)
    rec.out_net = edit_picture(rec.ws_net, "-Z(6)9.99")

    # DISPLAY "SUBTOTAL: " OUT-SUBTOTAL  (concatenation, no separator)
    output_lines.append("SUBTOTAL: " + rec.out_subtotal)
    # DISPLAY "DISCOUNT: " OUT-DISC
    output_lines.append("DISCOUNT: " + rec.out_disc)
    # DISPLAY "NET:     " OUT-NET
    output_lines.append("NET:     " + rec.out_net)

    return "\n".join(output_lines)


# ---------------------------------------------------------------------------
# Module entry point
# ---------------------------------------------------------------------------

def main(input_line: str) -> str:
    """Run the INVOICE program on one input line and return its DISPLAY output.

    Lines are joined by "\n" with NO trailing newline. Never raises.
    """
    rec = InvoiceRecord()
    try:
        return main_para(rec, input_line)
    except Exception:
        # COBOL does not crash on odd input; return empty output on unexpected error.
        return ""


if __name__ == "__main__":
    import sys

    line = sys.stdin.readline()
    if line.endswith("\n"):
        line = line[:-1]
    print(main(line), end="")
