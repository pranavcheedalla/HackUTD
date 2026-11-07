"""Migration of COBOL program 'interest' to Python 3.11.

Reads one pipe-delimited line (principal|rate|years), validates each token,
computes simple interest = principal * rate * years / 100 with ROUNDED storage,
and prints INTEREST=<edited 10-char field> or an error line.
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
# COBOL working-storage fields (mirror of the original data division)
# ---------------------------------------------------------------------------

class InterestState:
    """Holds COBOL working-storage state between paragraphs."""

    def __init__(self):
        self.input_line = " " * 256          # PIC X(256)
        self.raw_principal = " " * 256       # PIC X(256)
        self.raw_rate = " " * 256            # PIC X(256)
        self.raw_years = " " * 256           # PIC X(256)
        self.token_text = " " * 256          # PIC X(256)
        self.principal_amount = Decimal(0)   # PIC 9(5)V99
        self.annual_rate = Decimal(0)        # PIC 9(3)V99
        self.years_count = Decimal(0)        # PIC 99
        self.interest_amount = Decimal(0)    # PIC 9(7)V99
        self.printed_interest = ""           # PIC 9(7).99  (edited)
        self.valid_input = Decimal(1)        # PIC 9 value 1
        self.delimiter_count = 0             # binary-long
        self.token_length = 0                # binary-long
        self.digit_index = 0                 # binary-long
        self.whole_digits = 0                # binary-long
        self.fraction_digits = 0             # binary-long
        self.max_whole = 0                   # binary-long
        self.max_fraction = 0                # binary-long
        self.dot_seen = Decimal(0)           # PIC 9


# ---------------------------------------------------------------------------
# Paragraph: validate-number
# ---------------------------------------------------------------------------

def validate_number(state: InterestState) -> None:
    """validate-number paragraph.

    Validates token_text character-by-character against max_whole / max_fraction.
    Sets valid_input to 0 on any invalid character or digit-count violation.
    NOTE: valid_input is never reset back to 1 here (COBOL quirk #9).
    """
    # compute token-length = length(trim(token-text))   -- trim removes ASCII spaces only
    trimmed = state.token_text.strip(" ")
    state.token_length = len(trimmed)

    state.whole_digits = 0
    state.fraction_digits = 0
    state.dot_seen = Decimal(0)

    state.digit_index = 1
    while state.digit_index <= state.token_length:
        ch = state.token_text[state.digit_index - 1]  # COBOL is 1-based
        if "0" <= ch <= "9":
            if state.dot_seen == 0:
                state.whole_digits += 1
            else:
                state.fraction_digits += 1
        elif ch == ".":
            if state.dot_seen == 1 or state.max_fraction == 0:
                state.valid_input = Decimal(0)
            state.dot_seen = Decimal(1)
        else:
            # when other: any non-digit, non-dot character invalidates
            state.valid_input = Decimal(0)
        state.digit_index += 1

    if (
        state.whole_digits == 0
        or state.whole_digits > state.max_whole
        or state.fraction_digits > state.max_fraction
        or (state.dot_seen == 1 and state.fraction_digits == 0)
    ):
        state.valid_input = Decimal(0)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(input_line: str) -> str:
    """Return everything the COBOL program would print, lines joined by "\n",
    with NO trailing newline. Never raises."""
    state = InterestState()

    # ACCEPT input-line  (into 256-char buffer; short lines padded with spaces)
    state.input_line = input_line[:256].ljust(256)

    # inspect input-line tallying delimiter-count for all "|"
    state.delimiter_count = state.input_line.count("|")

    if state.delimiter_count != 2:
        return "ERROR:INVALID_INPUT"

    # unstring input-line delimited by "|" into raw-principal raw-rate raw-years
    parts = state.input_line.split("|")
    # COBOL UNSTRING fills the three receiving fields left-to-right;
    # extra tokens are ignored, missing ones stay spaces.
    state.raw_principal = (parts[0] if len(parts) > 0 else " ")[:256].ljust(256)
    state.raw_rate = (parts[1] if len(parts) > 1 else " ")[:256].ljust(256)
    state.raw_years = (parts[2] if len(parts) > 2 else " ")[:256].ljust(256)

    # ---- validate principal ----
    # move trim(raw-principal) to token-text
    state.token_text = state.raw_principal.strip(" ")
    state.max_whole = 5
    state.max_fraction = 2
    validate_number(state)

    # ---- validate rate ----
    state.token_text = state.raw_rate.strip(" ")
    state.max_whole = 3
    state.max_fraction = 2
    validate_number(state)

    # ---- validate years ----
    state.token_text = state.raw_years.strip(" ")
    state.max_whole = 2
    state.max_fraction = 0
    validate_number(state)

    if state.valid_input == 0:
        return "ERROR:INVALID_INPUT"

    # move numval(raw-principal) to principal-amount
    # NUMVAL parses human-readable text; raw fields were already validated
    state.principal_amount = pic_store(
        Decimal(state.raw_principal.strip(" ")), 5, 2, signed=False
    )
    # move numval(raw-rate) to annual-rate
    state.annual_rate = pic_store(
        Decimal(state.raw_rate.strip(" ")), 3, 2, signed=False
    )
    # move numval(raw-years) to years-count
    state.years_count = pic_store(
        Decimal(state.raw_years.strip(" ")), 2, 0, signed=False
    )

    # if annual-rate > 100 -> invalid
    if state.annual_rate > Decimal(100):
        return "ERROR:INVALID_INPUT"

    # compute interest-amount rounded = principal * rate * years / 100
    #   on size error -> ERROR:OVERFLOW
    # Intermediate expression keeps full precision; truncation/rounding only at store.
    product = state.principal_amount * state.annual_rate * state.years_count / Decimal(100)
    # Check overflow against PIC 9(7)V99 capacity (9999999.99) before storing.
    # COBOL ON SIZE ERROR triggers when the rounded result doesn't fit.
    rounded_product = product.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if abs(rounded_product) >= Decimal(10) ** 7:
        return "ERROR:OVERFLOW"
    state.interest_amount = pic_store(
        rounded_product, 7, 2, signed=False, rounded=True
    )

    # move interest-amount to printed-interest   (PIC 9(7).99 edited)
    # PIC 9(7).99 has no Z suppression -> exactly 10 chars, leading zeros kept.
    state.printed_interest = edit_picture(state.interest_amount, "9(7).99")

    # display "INTEREST=" printed-interest
    return "INTEREST=" + state.printed_interest


# ---------------------------------------------------------------------------
# Allow direct execution: python interest.py < input.txt
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    line = sys.stdin.readline()
    # Strip only the trailing newline; COBOL ACCEPT does not strip other whitespace.
    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    print(main(line), end="")
