# 2 test(s) quarantined for review: test_known_interest_exact, test_larger_known_interest_exact
"""Boundary and error-handling tests for modern.interest.main.

These tests do not attempt byte-for-byte equivalence with COBOL (that is
covered elsewhere).  They assert properties that follow directly from the
spec: no exceptions, str output, determinism, fixed output widths, the
years==0 error branch, monotonicity where implied, and a few exactly
computable values.
"""

import pytest
from decimal import Decimal

from modern.interest import main

# ---------------------------------------------------------------------------
# Helpers to build spec-conformant 15-character input lines
# ---------------------------------------------------------------------------

def line(principal: str, rate: str, years: str) -> str:
    """Concatenate fixed-width fields: principal(9), rate(4), years(2)."""
    return principal + rate + years


# ---------------------------------------------------------------------------
# 1. main never raises and always returns a str
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "",                                  # blank / short input
        " ",                                 # all spaces
        "000000000000000",                   # all zeros (15 chars)
        "00000000000000",                    # 14 chars (short by one)
        "0000000000000000",                  # 16 chars (extra-long)
        "999999999999999",                   # max field sizes, all 9s
        "00000010000001",                    # smallest non-zero: 0.01 principal, 0.00 rate, 01 year
        "00000000100001",                    # rate 0.01, years 01
        "00000000000101",                    # years 01 only
        "123456789012345678901234567890",    # very long input
        "abcdefghijklmno",                   # non-numeric garbage
        "  10000  0501",                     # embedded spaces
        "-00000010000001",                   # negative-looking text (unsigned fields)
    ],
)
def test_main_never_raises_returns_str(input_line):
    result = main(input_line)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 2. Determinism
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "000000000000000",
        "00000010000001",
        "999999999999999",
        "00000010005002",
        "00001000005010",
    ],
)
def test_main_is_deterministic(input_line):
    assert main(input_line) == main(input_line)


# ---------------------------------------------------------------------------
# 3. Fixed-width output lines keep the same length across inputs
# ---------------------------------------------------------------------------

# Spec: "INTEREST: " (10 chars) + OUT-INTEREST (10 chars) = 20 chars.
# Spec: "TOTAL:    " (10 chars) + OUT-TOTAL (11 chars) = 21 chars.
INTEREST_LINE_LEN = 20
TOTAL_LINE_LEN = 21


@pytest.mark.parametrize(
    "input_line",
    [
        "000000000000000",   # zero principal, zero rate, zero years -> error branch
        "00000010000001",    # smallest non-zero principal, 1 year
        "00000010005002",    # principal 1.00, rate 5.00, 2 years
        "999999999999999",   # max fields
        "00001000005010",    # principal 100.00, rate 5.00, 10 years
    ],
)
def test_output_line_lengths_are_fixed(input_line):
    result = main(input_line)
    if result == "":
        # Empty string only from the safety fallback; skip length checks.
        return
    lines = result.split("\n")
    if lines[0].startswith("ERROR:"):
        return  # error branch has a single line of different length
    assert len(lines[0]) == INTEREST_LINE_LEN, lines[0]
    assert len(lines[1]) == TOTAL_LINE_LEN, lines[1]


# ---------------------------------------------------------------------------
# 4. Error branch: years == 0
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "00000000000000",   # all zeros
        "00000010000000",   # principal 1.00, rate 0.00, years 00
        "99999999999900",   # max principal/rate, years 00
        "00000000100000",   # rate 0.01, years 00
    ],
)
def test_years_zero_takes_error_branch(input_line):
    result = main(input_line)
    assert "ERROR: YEARS MUST BE AT LEAST 1" in result
    # Spec: no arithmetic is performed; the program stops after the error.
    assert result.count("\n") == 0


# ---------------------------------------------------------------------------
# 5. Exactly computable values from the spec
# ---------------------------------------------------------------------------

# principal 0.00, rate 0.00, years 01 -> interest 0.00, total 0.00.
# Spec edge case: interest of exactly 0.00 displays as "      0.00" (6 spaces).
# Total 0.00 under Z(7)9.99 -> "       0.00" (7 spaces).
def test_zero_principal_zero_rate_one_year_exact():
    result = main(line("000000000", "0000", "01"))
    assert result == "INTEREST:       0.00\nTOTAL:           0.00"


# principal 100.00, rate 5.00, years 01 -> interest = 100*5*1/100 = 5.00 exactly.
# OUT-INTEREST Z(6)9.99 -> "     5.00" (5 spaces). Total 105.00 -> "   105.00".
@pytest.mark.skip(reason='QUARANTINED for human review: disagrees with the module that matches the real COBOL on every recorded case')
def test_known_interest_exact():
    result = main(line("000010000", "0005", "01"))
    assert result == "INTEREST:      5.00\nTOTAL:     105.00"


# principal 10000.00, rate 5.00, years 02 -> interest = 10000*5*2/100 = 1000.00 exactly.
# OUT-INTEREST -> "  1000.00". Total 11000.00 -> "  11000.00".
@pytest.mark.skip(reason='QUARANTINED for human review: disagrees with the module that matches the real COBOL on every recorded case')
def test_larger_known_interest_exact():
    result = main(line("000100000", "0005", "02"))
    assert result == "INTEREST:   1000.00\nTOTAL:    11000.00"


# ---------------------------------------------------------------------------
# 6. Monotonicity: more principal never yields less interest (same rate/years)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "principal_low, principal_high",
    [
        ("000000000", "000000100"),   # 0.00 vs 1.00
        ("000000100", "000005000"),   # 1.00 vs 50.00
        ("000005000", "000100000"),   # 50.00 vs 1000.00
        ("000100000", "999999999"),   # 1000.00 vs max
    ],
)
def test_more_principal_never_less_interest(principal_low, principal_high):
    rate = "0005"   # 5.00%
    years = "02"    # 2 years

    def interest_value(input_line):
        result = main(line(input_line, rate, years))
        # Parse the numeric portion after "INTEREST: "
        return result.split("\n")[0].split("INTEREST: ")[1]

    low_interest = interest_value(principal_low)
    high_interest = interest_value(principal_high)

    # Compare as Decimal after stripping spaces.
    low_dec = Decimal(low_interest.replace(" ", ""))
    high_dec = Decimal(high_interest.replace(" ", ""))
    assert high_dec >= low_dec


# ---------------------------------------------------------------------------
# 7. Monotonicity: more years never yields less interest (same principal/rate)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "years_low, years_high",
    [
        ("01", "02"),
        ("02", "05"),
        ("05", "99"),
    ],
)
def test_more_years_never_less_interest(years_low, years_high):
    principal = "000010000"  # 100.00
    rate = "0010"            # 10.00%

    def interest_value(input_line):
        result = main(line(principal, rate, input_line))
        return result.split("\n")[0].split("INTEREST: ")[1]

    low_dec = Decimal(interest_value(years_low).replace(" ", ""))
    high_dec = Decimal(interest_value(years_high).replace(" ", ""))
    assert high_dec >= low_dec


# ---------------------------------------------------------------------------
# 8. Total >= principal (interest is non-negative for valid inputs)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        line("000000100", "0005", "01"),
        line("000010000", "0010", "05"),
        line("999999999", "9999", "99"),
    ],
)
def test_total_at_least_principal(input_line):
    result = main(input_line)
    if result.startswith("ERROR:"):
        return
    interest_line, total_line = result.split("\n")
    interest_str = interest_line.split("INTEREST: ")[1].replace(" ", "")
    total_str = total_line.split("TOTAL:    ")[1].replace(" ", "")

    interest = Decimal(interest_str)
    total = Decimal(total_str)
    # principal is embedded in input_line cols 1-9
    principal_raw = input_line[:9]
    principal = Decimal(int(principal_raw.replace(" ", "0") or "0")) / Decimal(100)
    assert total >= principal
    assert interest >= Decimal("0")


# ---------------------------------------------------------------------------
# 9. Short / blank input behaves safely (padded with spaces -> zeros)
# ---------------------------------------------------------------------------

def test_blank_input_error_branch():
    # 15 spaces -> all fields zero -> years == 0 -> error branch
    result = main("               ")
    assert "ERROR: YEARS MUST BE AT LEAST 1" in result


def test_short_input_padded_safely():
    result = main("0000001")  # only 7 chars; rest padded with spaces
    assert isinstance(result, str)
    # Should not raise; either error branch (years spaces->0) or computed output.


# ---------------------------------------------------------------------------
# 10. Extra-long input is truncated safely
# ---------------------------------------------------------------------------

def test_extra_long_input_truncated_safely():
    result = main("9" * 100)
    assert isinstance(result, str)
    # All fields become 9s -> years 99 != 0, so computed output (or wrap).
    # Just assert it returns without exception.
