"""payroll - COBOL payroll program migrated to Python 3.11.

Byte-for-byte equivalent DISPLAY output for every input line.
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
# Payroll module
# ---------------------------------------------------------------------------

class _PayrollState:
    """Working-storage for one payroll run (COBOL working-storage section)."""

    def __init__(self) -> None:
        self.input_line: str = ""
        self.raw_hours: str = ""
        self.raw_rate: str = ""
        self.token_text: str = ""
        self.hours_worked: Decimal = Decimal("0")
        self.hourly_rate: Decimal = Decimal("0")
        self.gross_pay: Decimal = Decimal("0")
        self.tax_amount: Decimal = Decimal("0")
        self.net_pay: Decimal = Decimal("0")
        self.printed_gross: str = ""
        self.printed_tax: str = ""
        self.printed_net: str = ""
        self.valid_input: int = 1          # PIC 9 value 1
        self.delimiter_count: int = 0      # binary-long
        self.token_length: int = 0         # binary-long
        self.digit_index: int = 0          # binary-long
        self.whole_digits: int = 0         # binary-long
        self.fraction_digits: int = 0      # binary-long
        self.dot_seen: int = 0             # PIC 9


def _trim(text: str) -> str:
    """COBOL FUNCTION TRIM removes ASCII spaces only."""
    return text.strip(" ")


def _numval(text: str) -> Decimal:
    """COBOL FUNCTION NUMVAL: parse a human-readable number like '123.45'.

    Returns Decimal('0') for anything that is not a valid unsigned numeric
    literal (digits plus at most one decimal point)."""
    s = text.strip(" ")
    if not s:
        return Decimal("0")
    # Reject anything that is not digits and at most one dot
    dot_count = s.count(".")
    if dot_count > 1:
        return Decimal("0")
    for ch in s:
        if ch not in "0123456789.":
            return Decimal("0")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def _validate_number(state: _PayrollState) -> None:
    """COBOL paragraph validate-number.

    Scans token-text character by character.  valid_input is an AND-style
    flag: once set to 0 it never goes back to 1 within this paragraph.
    """
    state.token_length = len(_trim(state.token_text))
    state.whole_digits = 0
    state.fraction_digits = 0
    state.dot_seen = 0

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
                state.valid_input = 0
            state.dot_seen = 1
        else:
            state.valid_input = 0
        state.digit_index += 1

    if (
        state.whole_digits == 0
        or state.whole_digits > 3
        or state.fraction_digits > 2
        or (state.dot_seen == 1 and state.fraction_digits == 0)
    ):
        state.valid_input = 0


def main(input_line: str) -> str:
    """Return everything the COBOL program would print, lines joined by "\n",
    no trailing newline."""
    state = _PayrollState()

    # ACCEPT input-line  (PIC X(256) buffer; short line padded with spaces)
    state.input_line = input_line[:256].ljust(256)

    # INSPECT input-line tallying delimiter-count for all "|"
    state.delimiter_count = state.input_line.count("|")

    if state.delimiter_count != 1:
        return "ERROR:INVALID_INPUT"

    # UNSTRING input-line delimited by "|" into raw-hours raw-rate
    # No trimming occurs during UNSTRING.
    parts = state.input_line.split("|", 1)
    state.raw_hours = parts[0]
    state.raw_rate = parts[1] if len(parts) > 1 else ""

    # MOVE trim(raw-hours) to token-text ; perform validate-number
    state.token_text = _trim(state.raw_hours)
    _validate_number(state)

    # MOVE trim(raw-rate) to token-text ; perform validate-number
    state.token_text = _trim(state.raw_rate)
    _validate_number(state)

    if state.valid_input == 0:
        return "ERROR:INVALID_INPUT"

    # MOVE numval(raw-hours) to hours-worked   (PIC 9(3)V99, unsigned)
    state.hours_worked = pic_store(_numval(state.raw_hours), 3, 2, signed=False)
    # MOVE numval(raw-rate) to hourly-rate     (PIC 9(3)V99, unsigned)
    state.hourly_rate = pic_store(_numval(state.raw_rate), 3, 2, signed=False)

    # Round gross once, after combining regular and overtime earnings.
    if state.hours_worked > Decimal("40"):
        # COMPUTE gross-pay ROUNDED = ... ON SIZE ERROR ...
        # Intermediate keeps full precision; truncation happens at store.
        intermediate = (
            Decimal("40") * state.hourly_rate
            + (state.hours_worked - Decimal("40")) * state.hourly_rate * Decimal("1.5")
        )
        state.gross_pay = pic_store(intermediate, 7, 2, signed=False, rounded=True)
        # COBOL has ON SIZE ERROR only for this compute; GnuCOBOL sets the
        # size-error condition when high-order digits are lost.  Replicate:
        if abs(intermediate) >= Decimal(10) ** 7:
            return "ERROR:OVERFLOW"
    else:
        intermediate = state.hours_worked * state.hourly_rate
        state.gross_pay = pic_store(intermediate, 7, 2, signed=False, rounded=True)

    # Progressive tax on rounded gross: 10%, then 20%, then 30%.
    if state.gross_pay <= Decimal("500"):
        intermediate = state.gross_pay * Decimal("0.10")
    elif state.gross_pay <= Decimal("1000"):
        intermediate = Decimal("50") + (state.gross_pay - Decimal("500")) * Decimal("0.20")
    else:
        intermediate = Decimal("150") + (state.gross_pay - Decimal("1000")) * Decimal("0.30")
    state.tax_amount = pic_store(intermediate, 7, 2, signed=False, rounded=True)

    # COMPUTE net-pay = gross-pay - tax-amount   (no ROUNDED, no ON SIZE ERROR)
    # NET-PAY is unsigned: negative result loses its sign -> absolute value.
    state.net_pay = pic_store(state.gross_pay - state.tax_amount, 7, 2, signed=False)

    # MOVE to display-edited fields PIC 9(7).99  (always 10 chars, leading zeros)
    state.printed_gross = edit_picture(state.gross_pay, "9(7).99")
    state.printed_tax = edit_picture(state.tax_amount, "9(7).99")
    state.printed_net = edit_picture(state.net_pay, "9(7).99")

    # DISPLAY "GROSS=" printed-gross "|TAX=" printed-tax "|NET=" printed-net
    return "GROSS=" + state.printed_gross + "|TAX=" + state.printed_tax + "|NET=" + state.printed_net


if __name__ == "__main__":
    import sys

    line = sys.stdin.readline()
    # Strip only the trailing newline; keep everything else exactly as received.
    if line.endswith("\n"):
        line = line[:-1]
    print(main(line), end="")
