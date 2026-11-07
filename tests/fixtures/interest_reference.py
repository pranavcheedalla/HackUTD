"""Handwritten Decimal fixture for the Person 2 integration smoke, not an agent rewrite."""

from decimal import Decimal, ROUND_HALF_UP
import re


def main(input_line: str) -> str:
    fields = [value.strip(" ") for value in input_line.split("|")]
    patterns = (r"[0-9]{1,5}(?:\.[0-9]{1,2})?",
                r"[0-9]{1,3}(?:\.[0-9]{1,2})?", r"[0-9]{1,2}")
    if len(fields) != 3 or not all(
        re.fullmatch(pattern, value) for pattern, value in zip(patterns, fields)
    ):
        return "ERROR:INVALID_INPUT"
    principal, rate, years = map(Decimal, fields)
    if rate > 100:
        return "ERROR:INVALID_INPUT"
    interest = (principal * rate * years / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    )
    return f"INTEREST={interest:010.2f}"
