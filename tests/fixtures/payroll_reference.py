"""Independent handwritten audit fixture; not Person 4's generated rewrite.

The production golden recorder never imports or calculates answers with this.
Tax is accumulated by slices to check the COBOL's piecewise arithmetic.
"""

from decimal import Decimal, ROUND_HALF_UP
import re

CENT = Decimal("0.01")
REGULAR_HOURS = Decimal("40")
OVERTIME_FACTOR = Decimal("1.5")
TAX_SLICES = (
    (Decimal("500"), Decimal("0.10")),
    (Decimal("500"), Decimal("0.20")),
    (None, Decimal("0.30")),
)


def main(input_line: str) -> str:
    fields = input_line.split("|")
    if len(fields) != 2:
        return "ERROR:INVALID_INPUT"
    fields = [value.strip(" ") for value in fields]
    if not all(re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,2})?", value) for value in fields):
        return "ERROR:INVALID_INPUT"
    hours, rate = map(Decimal, fields)
    regular = min(hours, REGULAR_HOURS) * rate
    overtime = max(hours - REGULAR_HOURS, Decimal("0")) * rate * OVERTIME_FACTOR
    gross = (regular + overtime).quantize(CENT, rounding=ROUND_HALF_UP)
    remaining = gross
    tax = Decimal("0")
    for width, percentage in TAX_SLICES:
        portion = remaining if width is None else min(remaining, width)
        tax += portion * percentage
        remaining -= portion
    tax = tax.quantize(CENT, rounding=ROUND_HALF_UP)
    net = gross - tax
    return f"GROSS={gross:010.2f}|TAX={tax:010.2f}|NET={net:010.2f}"
