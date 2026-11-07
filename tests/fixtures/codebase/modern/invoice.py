"""Hand-written reference for samples/legacy/invoice.cbl (uses COPY INVREC and CALL 'DISCOUNT').

Shows the caller convention from contract.py: import the callee's module by its
module_id and use its call(); modern/ is on sys.path during equivalence tests.
Valid numeric fixed-width records only (12 chars: qty 9(4), price 9(5)V99, tier X).
"""
from decimal import Decimal, ROUND_DOWN

import discount


def _store(value: Decimal, int_digits: int, dec_digits: int, signed: bool = False) -> Decimal:
    q = Decimal(1).scaleb(-dec_digits)
    v = Decimal(value).quantize(q, rounding=ROUND_DOWN)
    magnitude = (abs(v) % (Decimal(10) ** int_digits)).quantize(q)
    return -magnitude if (signed and v < 0) else magnitude


def _z_edit(value: Decimal, int_digits: int) -> str:
    """PIC Z(n-1)9.99: leading zeros suppressed, at least one integer digit."""
    whole, frac = f"{abs(value):.2f}".split(".")
    return f"{int(whole):>{int_digits}}.{frac}"


def _digits(text: str) -> int:
    """Numeric DISPLAY field read by ACCEPT: GnuCOBOL treats blank positions as zero."""
    return int(text.replace(" ", "0"))


def main(input_line: str) -> str:
    record = input_line[:12].ljust(12)
    qty = Decimal(_digits(record[0:4]))
    price = Decimal(_digits(record[4:11])) / 100
    tier = record[11]
    if qty == 0:
        return "ERROR: QUANTITY MUST BE AT LEAST 1"
    exact = qty * price
    if exact > Decimal("9999999.99"):
        return "ERROR: SUBTOTAL TOO LARGE"
    subtotal = _store(exact, 7, 2)
    _, subtotal, rate = discount.call(tier, subtotal, Decimal("0"))
    disc_amt = _store(subtotal * rate / 100, 5, 2)
    net = _store(subtotal - disc_amt, 7, 2, signed=True)
    sign = "-" if net < 0 else " "
    return "\n".join([
        "SUBTOTAL: " + _z_edit(subtotal, 7),
        "DISCOUNT: " + _z_edit(disc_amt, 5),
        "NET:     " + sign + _z_edit(net, 7),
    ])
