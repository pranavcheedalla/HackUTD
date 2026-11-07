"""Hand-written reference rewrite of p4_interest.cbl (used for --offline and to build expected outputs)."""
from decimal import Decimal
from agents.cobol_helpers import pic_from_text, pic_store, split_fixed, edit_picture


def main(input_line: str) -> str:
    principal_s, rate_s, years_s = split_fixed(input_line, [9, 4, 2])  # WS-INPUT group
    principal = pic_from_text(principal_s, 7, 2)
    rate = pic_from_text(rate_s, 2, 2)
    years = pic_from_text(years_s, 2, 0)
    if years == 0:
        return "ERROR: YEARS MUST BE GREATER THAN ZERO"
    interest = pic_store(principal * rate * years / Decimal(100), 7, 2)  # truncates, no ROUNDED
    total = pic_store(principal + interest, 8, 2)
    return "INTEREST=" + edit_picture(interest, "Z,ZZZ,ZZ9.99") + " TOTAL=" + edit_picture(total, "ZZ,ZZZ,ZZ9.99")
