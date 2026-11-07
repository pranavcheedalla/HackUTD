"""Hand-written reference for samples/legacy/interest.cbl (fixed-format, fixed-width input).

Valid numeric records only (15 chars: principal 9(7)V99, rate 9(2)V99, years 9(2)).
"""
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP


def _z_edit(value: Decimal, int_digits: int) -> str:
    whole, frac = f"{value:.2f}".split(".")
    return f"{int(whole):>{int_digits}}.{frac}"


def _digits(text: str) -> int:
    """Numeric DISPLAY field read by ACCEPT: GnuCOBOL treats blank positions as zero."""
    return int(text.replace(" ", "0"))


def main(input_line: str) -> str:
    record = input_line[:15].ljust(15)
    principal = Decimal(_digits(record[0:9])) / 100
    rate = Decimal(_digits(record[9:13])) / 100
    years = Decimal(_digits(record[13:15]))
    if years == 0:
        return "ERROR: YEARS MUST BE AT LEAST 1"
    interest = (principal * rate * years / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    interest = interest % Decimal(10) ** 7
    total = ((principal + interest) % Decimal(10) ** 8).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    return "INTEREST: " + _z_edit(interest, 7) + "\nTOTAL:    " + _z_edit(total, 8)
