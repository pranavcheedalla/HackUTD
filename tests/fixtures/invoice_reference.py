"""Handwritten Decimal audit fixture; the golden recorder never imports this."""

from decimal import Decimal, ROUND_DOWN
import re


def main(input_line: str) -> str:
    fields = [value.strip(" ") for value in input_line.split("|")]
    patterns = (r"[0-9]{1,3}", r"[0-9]{1,5}(?:\.[0-9]{1,2})?",
                r"[0-9]{1,3}(?:\.[0-9]{1,2})?")
    if len(fields) != 3 or not all(
        re.fullmatch(pattern, value) for pattern, value in zip(patterns, fields)
    ):
        return "ERROR:INVALID_INPUT"
    quantity, price, discount = map(Decimal, fields)
    if discount > 100:
        return "ERROR:INVALID_INPUT"
    exact = quantity * price * (100 - discount) / 100
    total = exact.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    if total > Decimal("99999.99"):
        return "ERROR:OVERFLOW"
    return f"TOTAL={total:08.2f}"
