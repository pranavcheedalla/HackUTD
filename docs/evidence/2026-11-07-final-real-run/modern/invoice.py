"""COBOL invoice processor migrated to Python 3.11.

Byte-for-byte equivalent DISPLAY output for the original GnuCOBOL program.
All numeric storage uses decimal.Decimal; truncation happens at every store,
matching COBOL MOVE/COMPUTE semantics exactly.
"""

from decimal import Decimal, ROUND_DOWN


# ---------------------------------------------------------------------------
# COBOL data-semantics helpers (copied verbatim per migration standard)
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
    digits = "".join(ch for ch in text.replace(" ", "0") if ch.isdigit()) or "0"
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
    return __import__("re").sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic.upper())


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
# Invoice module
# ---------------------------------------------------------------------------

def _validate_number(token_text, max_whole, max_fraction, valid_input):
    """COBOL paragraph VALIDATE-NUMBER.

    Validates digit-by-digit; never resets an invalid flag back to valid.
    """
    # compute token-length = length(trim(token-text))
    token_text = token_text.strip(" ")
    token_length = len(token_text)

    whole_digits = 0
    fraction_digits = 0
    dot_seen = 0

    for digit_index in range(token_length):
        ch = token_text[digit_index]
        if "0" <= ch <= "9":
            if dot_seen == 0:
                whole_digits += 1
            else:
                fraction_digits += 1
        elif ch == ".":
            if dot_seen == 1 or max_fraction == 0:
                valid_input = 0
            dot_seen = 1
        else:
            valid_input = 0

    if (
        whole_digits == 0
        or whole_digits > max_whole
        or fraction_digits > max_fraction
        or (dot_seen == 1 and fraction_digits == 0)
    ):
        valid_input = 0

    return valid_input


def main(input_line: str) -> str:
    """Return exactly what the COBOL program DISPLAYs (no trailing newline)."""
    # ACCEPT input-line  (PIC X(256) buffer; we keep the raw line as given)
    # Tally '|' delimiters
    delimiter_count = input_line.count("|")

    if delimiter_count != 2:
        return "ERROR:INVALID_INPUT"

    # UNSTRING input-line delimited by "|" into raw-quantity raw-price raw-discount
    raw_parts = input_line.split("|")
    # COBOL UNSTRING into exactly 3 receiving fields; extra delimiters would
    # overflow, but with exactly 2 delimiters we always get 3 tokens.
    raw_quantity = raw_parts[0]
    raw_price = raw_parts[1]
    raw_discount = raw_parts[2]

    valid_input = 1  # PIC 9 value 1

    # --- validate quantity ---
    token_text = raw_quantity.strip(" ")
    valid_input = _validate_number(token_text, 3, 0, valid_input)

    # --- validate price ---
    token_text = raw_price.strip(" ")
    valid_input = _validate_number(token_text, 5, 2, valid_input)

    # --- validate discount ---
    token_text = raw_discount.strip(" ")
    valid_input = _validate_number(token_text, 3, 2, valid_input)

    if valid_input == 0:
        return "ERROR:INVALID_INPUT"

    # Convert validated tokens with NUMVAL (human-readable parse)
    quantity_count = pic_store(Decimal(raw_quantity.strip(" ")), 3, 0, signed=False)
    unit_price = pic_store(Decimal(raw_price.strip(" ")), 5, 2, signed=False)
    discount_percent = pic_store(Decimal(raw_discount.strip(" ")), 3, 2, signed=False)

    if discount_percent > 100:
        return "ERROR:INVALID_INPUT"

    # COMPUTE exact-total = quantity-count * unit-price * (100 - discount-percent) / 100
    # Intermediate results keep full precision; truncation only at the store.
    exact_total_value = (
        quantity_count * unit_price * (Decimal(100) - discount_percent) / Decimal(100)
    )
    exact_total = pic_store(exact_total_value, 8, 6, signed=False)

    if exact_total >= Decimal(100000):
        return "ERROR:OVERFLOW"

    # MOVE exact-total to invoice-total (PIC 9(5)V99): truncates beyond 2 decimals,
    # silently drops high-order digits (no ON SIZE ERROR).
    invoice_total = pic_store(exact_total, 5, 2, signed=False)

    # MOVE invoice-total to printed-total (PIC 9(5).99)
    # Edited picture with all '9' digits -> zero-filled, 8 chars wide.
    printed_total = edit_picture(invoice_total, "9(5).99")

    return "TOTAL=" + printed_total


if __name__ == "__main__":
    import sys

    line = sys.stdin.readline()
    # Strip only the trailing newline, preserving any other characters exactly.
    if line.endswith("\n"):
        line = line[:-1]
    print(main(line), end="")
