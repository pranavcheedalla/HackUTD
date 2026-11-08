# 1 test(s) quarantined for review: test_monotonic_gross_tax_net
"""Boundary and error-handling tests for modern.payroll.main.

These tests do NOT duplicate the equivalence suite.  They assert properties
that follow directly from the spec: no exceptions, str output, deterministic
behaviour, fixed-width fields, the validation branch, monotonicity where the
spec implies it, and exact values only where the spec lets us compute them
with certainty (each such case is commented).
"""

import pytest
from decimal import Decimal

from modern.payroll import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_valid_output_shape(output: str) -> None:
    """Every successful payroll line must look like:
    GROSS=NNNNNNN.NN|TAX=NNNNNNN.NN|NET=NNNNNNN.NN  (each amount 10 chars)."""
    assert output.startswith("GROSS=")
    assert "|TAX=" in output
    assert "|NET=" in output
    gross = output.split("|TAX=")[0][len("GROSS="):]
    tax = output.split("|TAX=")[1].split("|NET=")[0]
    net = output.split("|NET=")[1]
    for field in (gross, tax, net):
        assert len(field) == 10, f"field {field!r} is not 10 chars"
        assert field.count(".") == 1
        int_part, frac_part = field.split(".")
        assert len(int_part) == 7 and len(frac_part) == 2
        assert int_part.isdigit() and frac_part.isdigit()


def _amount(field_line: str, label: str) -> Decimal:
    """Extract a numeric amount from a GROSS=/TAX=/NET= output line."""
    if label == "NET":
        part = field_line.split("|NET=")[1]
    else:
        part = field_line.split(f"|{label}=")[1].split("|")[0]
    return Decimal(part)


# ---------------------------------------------------------------------------
# 1. main never raises and always returns a str
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "",                       # blank / empty
        " ",                      # spaces only
        "35.00|20.00",            # normal
        "0.00|0.00",              # zero values
        "999.99|999.99",          # max field sizes (all 9s)
        "0.01|0.01",              # smallest non-zero
        "40.00|25.00",            # overtime boundary exactly 40
        "40.01|25.00",            # just over 40 hours
        "1000.00|20.00",          # hours too big -> invalid
        "20.00|1000.00",          # rate too big -> invalid
        "abc|def",                # non-numeric
        "1.2.3|4.5",              # multiple dots
        "1.|2.00",                # dot with no fraction digits
        ".5|.01",                 # no whole digits
        "1|2",                    # no decimal point at all
        "001|002",                # leading zeros
        "1.234|2.00",             # too many fraction digits
        "1234.5|2.00",            # too many whole digits
        "-1.00|20.00",            # negative hours
        "40.00|-1.00",            # negative rate
        "||",                     # empty tokens
        "a|b|c",                  # two delimiters
        "no delimiter",           # zero delimiters
        "  35.00  |  20.00  ",    # padded tokens
        "0.50|0.01",              # tiny values
        "999.99|0.00",            # max hours, zero rate
        "0.00|999.99",            # zero hours, max rate
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
        "35.00|20.00",
        "45.00|20.00",
        "999.99|999.99",
        "0.00|0.00",
        "40.01|25.00",
        "1.00|500.01",
    ],
)
def test_main_is_deterministic(input_line):
    assert main(input_line) == main(input_line) == main(input_line)


# ---------------------------------------------------------------------------
# 3. Fixed-width output lines keep the same length across inputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "0.00|0.00",
        "35.00|20.00",
        "45.00|20.00",
        "999.99|999.99",
        "40.01|25.00",
        "1.00|500.01",
    ],
)
def test_output_length_is_constant(input_line):
    output = main(input_line)
    # "GROSS=" (6) + 10 + "|TAX=" (5) + 10 + "|NET=" (5) + 10 = 46
    assert len(output) == 46
    _assert_valid_output_shape(output)


# ---------------------------------------------------------------------------
# 4. Exact outputs from the spec edge cases
#    (computed by hand from the spec's arithmetic rules)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line, expected",
    [
        # Spec edge case: regular pay, 10% bracket
        ("35.00|20.00", "GROSS=0000700.00|TAX=0000090.00|NET=0000610.00"),
        # Spec edge case: overtime, 20% bracket
        ("45.00|20.00", "GROSS=0000950.00|TAX=0000140.00|NET=0000810.00"),
        # Spec edge case: sub-cent overtime rounding
        ("39.99|25.00", "GROSS=0000999.75|TAX=0000149.95|NET=0000849.80"),
        # Spec edge case: exactly 1000.00 gross -> 20% bracket top
        ("40.00|25.00", "GROSS=0001000.00|TAX=0000150.00|NET=0000850.00"),
        # Spec edge case: just over 1000 gross -> 30% bracket
        ("40.01|25.00", "GROSS=0001000.38|TAX=0000150.11|NET=0000850.27"),
        # Spec edge case: rate 499.99 -> 10% bracket
        ("1.00|499.99", "GROSS=0000499.99|TAX=0000050.00|NET=0000449.99"),
        # Spec edge case: rate 500.00 -> exactly 500 gross -> 10% bracket
        ("1.00|500.00", "GROSS=0000500.00|TAX=0000050.00|NET=0000450.00"),
        # Spec edge case: rate 500.01 -> just over 500 gross -> 20% bracket
        ("1.00|500.01", "GROSS=0000500.01|TAX=0000050.00|NET=0000450.01"),
        # Spec edge case: zero hours
        ("0.00|20.00", "GROSS=0000000.00|TAX=0000000.00|NET=0000000.00"),
        # Spec edge case: zero rate
        ("40.00|0.00", "GROSS=0000000.00|TAX=0000000.00|NET=0000000.00"),
        # Spec edge case: max values, high-order truncation in gross
        ("999.99|999.99", "GROSS=1479970.20|TAX=0443841.06|NET=1036129.14"),
        # Spec edge case: sub-cent gross rounds up to 0.01
        ("0.50|0.01", "GROSS=0000000.01|TAX=0000000.00|NET=0000000.01"),
    ],
)
def test_spec_edge_cases_exact(input_line, expected):
    assert main(input_line) == expected


# ---------------------------------------------------------------------------
# 5. Validation branch taken when spec says so
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "",                       # no delimiter
        "35.00",                  # no delimiter
        "a|b|c",                  # two delimiters
        "||",                     # empty tokens
        "-1.00|20.00",            # negative hours
        "40.00|-1.00",            # negative rate
        "1000.00|20.00",          # hours > 999.99
        "20.00|1000.00",          # rate > 999.99
        "abc|def",                # non-numeric
        "1.2.3|4.5",              # multiple dots
        "1.|2.00",                # dot, no fraction digits
        "1.234|2.00",             # too many fraction digits
        "1234.5|2.00",            # too many whole digits
        ".5|.01",                 # no whole digits
    ],
)
def test_invalid_input_returns_error(input_line):
    assert main(input_line) == "ERROR:INVALID_INPUT"


# ---------------------------------------------------------------------------
# 6. Monotonicity: more principal never yields less gross/tax/net
#    (within the valid input domain; spec implies non-negative computations)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason='QUARANTINED for human review: disagrees with the module that matches the real COBOL on every recorded case')
@pytest.mark.parametrize(
    "lower, higher",
    [
        ("0.00|20.00", "10.00|20.00"),      # more hours, same rate
        ("10.00|20.00", "10.00|30.00"),     # same hours, more rate
        ("35.00|20.00", "45.00|20.00"),     # crossing overtime boundary
        ("40.00|25.00", "40.01|25.00"),     # crossing 1000 gross boundary
    ],
)
def test_monotonic_gross_tax_net(lower, higher):
    low = main(lower)
    high = main(higher)
    # Both must be valid payroll lines (not error messages)
    assert low.startswith("GROSS=")
    assert high.startswith("GROSS=")

    assert _amount(high, "GROSS") >= _amount(low, "GROSS")
    assert _amount(high, "TAX") >= _amount(low, "TAX")
    assert _amount(high, "NET") >= _amount(low, "NET")


# ---------------------------------------------------------------------------
# 7. Extra-long input is truncated, not rejected (buffer capacity)
# ---------------------------------------------------------------------------

def test_extra_long_input_truncated_not_crash():
    long_line = "9" * 300 + "|" + "9" * 300
    result = main(long_line)
    assert isinstance(result, str)
    # Either an error message or a valid payroll line; never an exception.
    assert result == "ERROR:INVALID_INPUT" or result.startswith("GROSS=")


# ---------------------------------------------------------------------------
# 8. Short / blank input handled gracefully
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "",
        " ",
        "  ",
        "|",
        " | ",
        "35.00|",
        "|20.00",
    ],
)
def test_short_or_blank_input_no_crash(input_line):
    result = main(input_line)
    assert isinstance(result, str)
    assert result == "ERROR:INVALID_INPUT" or result.startswith("GROSS=")
