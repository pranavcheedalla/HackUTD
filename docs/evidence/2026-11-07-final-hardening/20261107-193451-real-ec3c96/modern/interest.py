"""Migration of COBOL program 'interest' to Python 3.11.

Byte-for-byte DISPLAY equivalence is preserved for every input.
"""
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import re


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
# COBOL working-storage state (shared across paragraphs / calls)
# ---------------------------------------------------------------------------

class _WorkingStorage:
    """Mirrors COBOL WORKING-STORAGE for program 'interest'."""

    def __init__(self) -> None:
        self.input_line = " " * 256
        self.raw_principal = " " * 256
        self.raw_rate = " " * 256
        self.raw_years = " " * 256
        self.token_text = " " * 256
        self.principal_amount = Decimal("0")   # PIC 9(5)V99
        self.annual_rate = Decimal("0")        # PIC 9(3)V99
        self.years_count = Decimal("0")        # PIC 99
        self.interest_amount = Decimal("0")    # PIC 9(7)V99
        self.printed_interest = " " * 10       # PIC 9(7).99
        self.valid_input = Decimal("1")        # PIC 9 value 1
        self.delimiter_count = 0               # binary-long
        self.token_length = 0                  # binary-long
        self.digit_index = 0                   # binary-long
        self.whole_digits = 0                  # binary-long
        self.fraction_digits = 0               # binary-long
        self.max_whole = 0                     # binary-long
        self.max_fraction = 0                  # binary-long
        self.dot_seen = Decimal("0")           # PIC 9


# ---------------------------------------------------------------------------
# COBOL paragraphs
# ---------------------------------------------------------------------------

def validate_number(ws: _WorkingStorage) -> None:
    """Validate token-text against digit-count rules.

    Legacy quirk: valid_input is initialized once to 1 and only ever set to 0.
    It is never reset back to 1 inside this paragraph, so an earlier failure
    persists across later PERFORM calls.
    """
    # compute token-length = length(trim(token-text))
    ws.token_length = len(ws.token_text.strip(" "))

    ws.whole_digits = 0
    ws.fraction_digits = 0
    ws.dot_seen = Decimal("0")

    ws.digit_index = 1
    while ws.digit_index <= ws.token_length:
        ch = ws.token_text[ws.digit_index - 1 : ws.digit_index]
        if "0" <= ch <= "9":
            if ws.dot_seen == 0:
                ws.whole_digits += 1
            else:
                ws.fraction_digits += 1
        elif ch == ".":
            if ws.dot_seen == 1 or ws.max_fraction == 0:
                ws.valid_input = Decimal("0")
            ws.dot_seen = Decimal("1")
        else:
            # any other character (including '-') invalidates the token
            ws.valid_input = Decimal("0")
        ws.digit_index += 1

    if (
        ws.whole_digits == 0
        or ws.whole_digits > ws.max_whole
        or ws.fraction_digits > ws.max_fraction
        or (ws.dot_seen == 1 and ws.fraction_digits == 0)
    ):
        ws.valid_input = Decimal("0")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(input_line: str) -> str:
    """Return exactly what the COBOL program DISPLAYs (lines joined by '\n',
    no trailing newline). Never raises."""
    ws = _WorkingStorage()

    # ACCEPT input-line  (PIC X(256) buffer; short lines padded with spaces)
    ws.input_line = input_line[:256].ljust(256)

    # MAIN paragraph
    # inspect input-line tallying delimiter-count for all "|"
    ws.delimiter_count = ws.input_line.count("|")

    if ws.delimiter_count != 2:
        return "ERROR:INVALID_INPUT"

    # unstring input-line delimited by "|" into raw-principal raw-rate raw-years
    parts = ws.input_line.split("|")
    # COBOL UNSTRING into exactly 3 fields: first two tokens, remainder into last
    ws.raw_principal = parts[0][:256].ljust(256) if len(parts) > 0 else " " * 256
    ws.raw_rate = parts[1][:256].ljust(256) if len(parts) > 1 else " " * 256
    ws.raw_years = parts[2][:256].ljust(256) if len(parts) > 2 else " " * 256

    # validate principal
    ws.token_text = ws.raw_principal.strip(" ")
    ws.max_whole = 5
    ws.max_fraction = 2
    validate_number(ws)

    # validate rate
    ws.token_text = ws.raw_rate.strip(" ")
    ws.max_whole = 3
    ws.max_fraction = 2
    validate_number(ws)

    # validate years
    ws.token_text = ws.raw_years.strip(" ")
    ws.max_whole = 2
    ws.max_fraction = 0
    validate_number(ws)

    if ws.valid_input == 0:
        return "ERROR:INVALID_INPUT"

    # move numval(raw-*) into numeric fields
    # NUMVAL parses human-readable numbers; tokens are already validated
    ws.principal_amount = pic_store(
        Decimal(ws.raw_principal.strip(" ")), 5, 2, signed=False
    )
    ws.annual_rate = pic_store(
        Decimal(ws.raw_rate.strip(" ")), 3, 2, signed=False
    )
    ws.years_count = pic_store(
        Decimal(ws.raw_years.strip(" ")), 2, 0, signed=False
    )

    # annual-rate must not exceed 100
    if ws.annual_rate > Decimal("100"):
        return "ERROR:INVALID_INPUT"

    # compute interest-amount rounded = principal * rate * years / 100
    # on size error -> ERROR:OVERFLOW
    full_result = (
        ws.principal_amount * ws.annual_rate * ws.years_count / Decimal("100")
    )
    # target PIC 9(7)V99 holds max 9999999.99 -> 7 integer digits
    if abs(full_result) >= Decimal(10) ** 7:
        return "ERROR:OVERFLOW"
    ws.interest_amount = pic_store(full_result, 7, 2, signed=False, rounded=True)

    # move interest-amount to printed-interest (PIC 9(7).99)
    ws.printed_interest = edit_picture(ws.interest_amount, "9(7).99")

    # display "INTEREST=" printed-interest
    return "INTEREST=" + ws.printed_interest


if __name__ == "__main__":
    import sys

    line = sys.stdin.readline()
    if line.endswith("\n"):
        line = line[:-1]
    print(main(line), end="")
