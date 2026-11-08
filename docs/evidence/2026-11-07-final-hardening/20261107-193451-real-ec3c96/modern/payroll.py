"""payroll.py - Python migration of COBOL payroll program.

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
# Payroll program state (COBOL WORKING-STORAGE)
# ---------------------------------------------------------------------------

class _PayrollState:
    """Holds working-storage fields shared by paragraphs."""

    def __init__(self):
        self.input_line = ""
        self.raw_hours = ""
        self.raw_rate = ""
        self.token_text = ""
        self.hours_worked = Decimal("0")      # PIC 9(3)V99
        self.hourly_rate = Decimal("0")       # PIC 9(3)V99
        self.gross_pay = Decimal("0")         # PIC 9(7)V99
        self.tax_amount = Decimal("0")        # PIC 9(7)V99
        self.net_pay = Decimal("0")           # PIC 9(7)V99
        self.printed_gross = ""               # PIC 9(7).99
        self.printed_tax = ""                 # PIC 9(7).99
        self.printed_net = ""                 # PIC 9(7).99
        self.valid_input = Decimal("1")       # PIC 9 value 1
        self.delimiter_count = 0              # binary-long
        self.token_length = 0                 # binary-long
        self.digit_index = 0                  # binary-long
        self.whole_digits = 0                 # binary-long
        self.fraction_digits = 0              # binary-long
        self.dot_seen = Decimal("0")          # PIC 9


# ---------------------------------------------------------------------------
# Paragraph: validate-number
# ---------------------------------------------------------------------------

def validate_number(state: _PayrollState) -> None:
    """Validate token-text: digits 0-9, at most one '.', whole digits 1-3,
    fraction digits 0-2, dot requires at least one fraction digit."""
    # compute token-length = length(trim(token-text))
    state.token_length = len(state.token_text.strip(" "))
    state.whole_digits = 0
    state.fraction_digits = 0
    state.dot_seen = Decimal("0")

    state.digit_index = 1
    while state.digit_index <= state.token_length:
        ch = state.token_text[state.digit_index - 1 : state.digit_index]
        if "0" <= ch <= "9":
            if state.dot_seen == 0:
                state.whole_digits += 1
            else:
                state.fraction_digits += 1
        elif ch == ".":
            if state.dot_seen == 1:
                state.valid_input = Decimal("0")
            state.dot_seen = Decimal("1")
        else:
            state.valid_input = Decimal("0")
        state.digit_index += 1

    if (
        state.whole_digits == 0
        or state.whole_digits > 3
        or state.fraction_digits > 2
        or (state.dot_seen == 1 and state.fraction_digits == 0)
    ):
        state.valid_input = Decimal("0")


# ---------------------------------------------------------------------------
# Main program logic
# ---------------------------------------------------------------------------

def main(input_line: str) -> str:
    """Return everything the COBOL payroll program would print.

    Lines joined by "\n", NO trailing newline. Never raises.
    """
    state = _PayrollState()

    # ACCEPT input-line  (PIC X(256) buffer; short lines not padded)
    state.input_line = input_line[:256]

    # inspect input-line tallying delimiter-count for all "|"
    state.delimiter_count = state.input_line.count("|")

    # if delimiter-count not = 1 -> ERROR:INVALID_INPUT, stop run
    if state.delimiter_count != 1:
        return "ERROR:INVALID_INPUT"

    # unstring input-line delimited by "|" into raw-hours raw-rate
    parts = state.input_line.split("|")
    state.raw_hours = parts[0]
    state.raw_rate = parts[1] if len(parts) > 1 else ""

    # move trim(raw-hours) to token-text; perform validate-number
    state.token_text = state.raw_hours.strip(" ")
    validate_number(state)

    # move trim(raw-rate) to token-text; perform validate-number
    state.token_text = state.raw_rate.strip(" ")
    validate_number(state)

    # if valid-input = 0 -> ERROR:INVALID_INPUT, stop run
    if state.valid_input == 0:
        return "ERROR:INVALID_INPUT"

    # move numval(raw-hours) to hours-worked   (PIC 9(3)V99, truncates)
    state.hours_worked = pic_store(
        Decimal(state.raw_hours.strip(" ")), 3, 2, signed=False
    )
    # move numval(raw-rate) to hourly-rate     (PIC 9(3)V99, truncates)
    state.hourly_rate = pic_store(
        Decimal(state.raw_rate.strip(" ")), 3, 2, signed=False
    )

    # Round gross once, after combining regular and overtime earnings.
    if state.hours_worked > Decimal("40"):
        # compute gross-pay rounded = 40 * hourly-rate +
        #     (hours-worked - 40) * hourly-rate * 1.5
        #     on size error display "ERROR:OVERFLOW" stop run
        full = (
            Decimal("40") * state.hourly_rate
            + (state.hours_worked - Decimal("40")) * state.hourly_rate * Decimal("1.5")
        )
        # ON SIZE ERROR: integer part needs more than 7 digits
        if int(abs(full)) >= 10 ** 7:
            return "ERROR:OVERFLOW"
        state.gross_pay = pic_store(full, 7, 2, signed=False, rounded=True)
    else:
        # compute gross-pay rounded = hours-worked * hourly-rate
        full = state.hours_worked * state.hourly_rate
        state.gross_pay = pic_store(full, 7, 2, signed=False, rounded=True)

    # Progressive tax on rounded gross: 10%, then 20%, then 30%.
    if state.gross_pay <= Decimal("500"):
        full = state.gross_pay * Decimal("0.10")
        state.tax_amount = pic_store(full, 7, 2, signed=False, rounded=True)
    elif state.gross_pay <= Decimal("1000"):
        full = Decimal("50") + (state.gross_pay - Decimal("500")) * Decimal("0.20")
        state.tax_amount = pic_store(full, 7, 2, signed=False, rounded=True)
    else:
        full = Decimal("150") + (state.gross_pay - Decimal("1000")) * Decimal("0.30")
        state.tax_amount = pic_store(full, 7, 2, signed=False, rounded=True)

    # compute net-pay = gross-pay - tax-amount   (no ON SIZE ERROR: truncates)
    state.net_pay = pic_store(
        state.gross_pay - state.tax_amount, 7, 2, signed=False, rounded=False
    )

    # move gross-pay to printed-gross   (PIC 9(7).99 edited: leading zeros shown)
    state.printed_gross = edit_picture(state.gross_pay, "9(7).99")
    # move tax-amount to printed-tax
    state.printed_tax = edit_picture(state.tax_amount, "9(7).99")
    # move net-pay to printed-net
    state.printed_net = edit_picture(state.net_pay, "9(7).99")

    # display "GROSS=" printed-gross "|TAX=" printed-tax "|NET=" printed-net
    return "GROSS=" + state.printed_gross + "|TAX=" + state.printed_tax + "|NET=" + state.printed_net


if __name__ == "__main__":
    import sys

    line = sys.stdin.read().rstrip("\n")
    print(main(line))
