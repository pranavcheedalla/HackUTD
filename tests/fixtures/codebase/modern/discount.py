"""Hand-written reference for samples/legacy/discount.cbl (a CALLed subprogram).

Shows the subprogram convention from contract.py:
  call(*params)   params in USING order, returns all params after the CALL (BY REFERENCE)
  main(line)      driver format: "tier|subtotal|rate" -> "LK-TIER=..|LK-SUBTOTAL=..|LK-RATE=.."
"""
from decimal import Decimal, ROUND_DOWN


def _store(value: Decimal, int_digits: int, dec_digits: int) -> Decimal:
    q = Decimal(1).scaleb(-dec_digits)
    return (abs(Decimal(value)).quantize(q, rounding=ROUND_DOWN) % (Decimal(10) ** int_digits)).quantize(q)


def call(tier: str, subtotal: Decimal, rate: Decimal) -> tuple[str, Decimal, Decimal]:
    if tier == "G":
        rate = Decimal("12.50")
    elif tier == "S":
        rate = Decimal("7.25")
    elif subtotal >= Decimal("1000.00"):
        rate = Decimal("5.00")
    else:
        rate = Decimal("0")
    return tier, subtotal, _store(rate, 2, 2)


def _edit(value: Decimal, int_digits: int, dec_digits: int) -> str:
    text = f"{_store(value, int_digits, dec_digits):.{dec_digits}f}"
    whole, _, frac = text.partition(".")
    return whole.zfill(int_digits) + ("." + frac if dec_digits else "")


def main(input_line: str) -> str:
    tokens = (input_line.split("|") + ["", "", ""])[:3]
    tier = (tokens[0][:1] or " ")
    subtotal = _store(Decimal(tokens[1].strip() or "0"), 7, 2)
    rate = _store(Decimal(tokens[2].strip() or "0"), 2, 2)
    tier, subtotal, rate = call(tier, subtotal, rate)
    return f"LK-TIER={tier}|LK-SUBTOTAL={_edit(subtotal, 7, 2)}|LK-RATE={_edit(rate, 2, 2)}"
