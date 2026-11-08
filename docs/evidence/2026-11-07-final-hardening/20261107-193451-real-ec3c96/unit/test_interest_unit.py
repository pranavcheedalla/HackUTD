"""Boundary and error-handling tests for modern.interest.main.

These tests do not trust the implementation; they assert only properties
that follow from the specification, plus the exact outputs that are
computable with certainty from the spec's edge_cases list.
"""

import pytest

from modern.interest import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_valid_interest_line(output: str) -> bool:
    """True if output looks like INTEREST= followed by exactly 10 chars."""
    return output.startswith("INTEREST=") and len(output) == len("INTEREST=") + 10


# ---------------------------------------------------------------------------
# Never-raises / always-returns-str
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "",                              # blank / short input
        " ",                             # spaces only
        "|",                             # one delimiter
        "||",                            # two delimiters, empty tokens
        "1|2|3",                         # minimal tokens
        "99999.99|999.99|99",            # all max field sizes
        "0.00|0.00|0",                   # zeros
        "0.01|0.01|1",                   # smallest non-zero principal/rate
        "100000.00|5.00|1",              # principal whole digits exceed max
        "100.00|100.01|1",               # rate exceeds 100
        "99999.99|100.00|99",            # max compute (near overflow boundary)
        "-100.00|5.00|1",                # negative principal
        "100.00|-5.00|1",                # negative rate
        "100.00|5.00|-1",                # negative years
        "1.2.3|4.5|6",                   # multiple periods in a token
        "12|34|56|78",                   # extra-long (3 delimiters)
        "abc|def|ghi",                   # non-numeric tokens
        "1.|2.|3",                       # period with no fraction digits
        ".5|.5|1",                       # no whole digits
        "000001.00|5.00|1",              # leading zeros beyond digit limit
        "1000.00|5.00|2" + "x" * 300,    # input longer than 256 chars
    ],
)
def test_main_never_raises_and_returns_str(input_line):
    """Spec: main never raises and always returns a str."""
    result = main(input_line)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "1000.00|5.00|2",
        "2500.50|3.75|3",
        "99999.99|100.00|99",
        "0.00|5.00|2",
        "||",
        "100000.00|5.00|1",
    ],
)
def test_main_is_deterministic(input_line):
    """Same input must always produce the same output."""
    assert main(input_line) == main(input_line) == main(input_line)


# ---------------------------------------------------------------------------
# Fixed-width output length
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "0.00|0.00|0",
        "1000.00|5.00|2",
        "99999.99|100.00|99",
        "1.00|0.50|1",
    ],
)
def test_interest_output_has_fixed_width(input_line):
    """Spec: printed-interest is PIC 9(7).99, exactly 10 characters."""
    result = main(input_line)
    if result.startswith("INTEREST="):
        assert _is_valid_interest_line(result)
        assert len(result.split("=", 1)[1]) == 10


# ---------------------------------------------------------------------------
# Exact outputs from spec edge_cases (computed by hand from the spec)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line,expected",
    [
        # Spec edge_cases: exact results are certain.
        ("1000.00|5.00|2", "INTEREST=0000100.00"),   # 1000*5*2/100 = 100.00
        ("2500.50|3.75|3", "INTEREST=0000281.31"),   # 2500.50*3.75*3/100 = 281.30625 -> 281.31
        ("100.00|100.00|1", "INTEREST=0000100.00"),  # 100*100*1/100 = 100.00
        ("0.00|5.00|2", "INTEREST=0000000.00"),      # zero principal
        ("1000.00|0.00|2", "INTEREST=0000000.00"),   # zero rate
        ("1000.00|5.00|0", "INTEREST=0000000.00"),   # zero years
        ("99999.99|100.00|99", "INTEREST=9899999.01"), # max compute
        ("99999.99|0.01|1", "INTEREST=0000010.00"),   # 99999.99*0.01*1/100 = 9.999999 -> 10.00
        ("0.01|0.01|1", "INTEREST=0000000.00"),       # 0.01*0.01*1/100 = 0.000001 -> 0.00
        ("1.00|0.50|1", "INTEREST=0000000.01"),       # 1*0.5*1/100 = 0.005 -> 0.01 (ROUNDED)
    ],
)
def test_main_exact_outputs_from_spec(input_line, expected):
    """Exact outputs are asserted because the spec gives them explicitly."""
    assert main(input_line) == expected


# ---------------------------------------------------------------------------
# Error / validation branch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "1000.00|5.00",          # only one delimiter
        "1|2|3|4",               # three delimiters
        "100000.00|5.00|1",      # principal whole digits > 5
        "100.00|1000.00|1",      # rate whole digits > 3
        "100.00|5.00|100",       # years whole digits > 2
        "1.23|4.56|7.8",         # years has fraction digits (max 0)
        "1.|5.00|1",             # period with no fraction digit
        ".5|.5|1",               # no whole digits
        "-100.00|5.00|1",        # negative sign
        "100.00|-5.00|1",        # negative sign
        "100.00|5.00|-1",        # negative sign
        "100.00|100.01|1",       # rate > 100 after conversion
        "abc|def|ghi",           # non-numeric
        "1.2.3|4.5|6",           # multiple periods
    ],
)
def test_main_returns_invalid_input_for_bad_input(input_line):
    """Spec: validation failures display ERROR:INVALID_INPUT and stop."""
    assert main(input_line) == "ERROR:INVALID_INPUT"


# ---------------------------------------------------------------------------
# Overflow branch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        # Rate max whole digits is 3, so 999.99 is invalid input.
        # Use the largest valid rate (100.00) with max principal and years:
        # 99999.99 * 100.00 * 99 / 100 = 9899999.01 -> fits in PIC 9(7)V99.
        # To force overflow we need a result >= 10^7 while staying within
        # field limits; the spec's own max case (99999.99|100.00|99) yields
        # 9899999.01, which is below the overflow threshold, so no valid
        # input can trigger ERROR:OVERFLOW under the stated limits.
        # This test documents that boundary: overflow is unreachable.
        ("99999.99|100.00|99"),
    ],
)
def test_main_max_valid_input_does_not_overflow(input_line):
    """Spec: the largest valid compute (99999.99|100.00|99) stays within PIC 9(7)V99."""
    assert main(input_line) == "INTEREST=9899999.01"


# ---------------------------------------------------------------------------
# Monotonic rule: more principal never yields less interest
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lower,higher",
    [
        ("100.00|5.00|1", "200.00|5.00|1"),
        ("1.00|0.50|1", "2.00|0.50|1"),
        ("0.01|0.01|1", "0.02|0.01|1"),
    ],
)
def test_more_principal_never_yields_less_interest(lower, higher):
    """Spec implies monotonicity: interest = principal * rate * years / 100."""
    low_out = main(lower)
    high_out = main(higher)
    assert low_out.startswith("INTEREST=") and high_out.startswith("INTEREST=")
    low_val = float(low_out.split("=", 1)[1])
    high_val = float(high_out.split("=", 1)[1])
    assert high_val >= low_val


# ---------------------------------------------------------------------------
# Monotonic rule: more years never yields less interest
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lower,higher",
    [
        ("1000.00|5.00|1", "1000.00|5.00|2"),
        ("1.00|0.50|1", "1.00|0.50|2"),
    ],
)
def test_more_years_never_yields_less_interest(lower, higher):
    """Spec implies monotonicity in years count."""
    low_out = main(lower)
    high_out = main(higher)
    assert low_out.startswith("INTEREST=") and high_out.startswith("INTEREST=")
    low_val = float(low_out.split("=", 1)[1])
    high_val = float(high_out.split("=", 1)[1])
    assert high_val >= low_val


# ---------------------------------------------------------------------------
# Zero-filled output check
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "0.00|5.00|2",
        "1.00|0.50|1",
        "99999.99|100.00|99",
    ],
)
def test_interest_output_is_zero_filled(input_line):
    """Spec: PIC 9 output is zero-filled, no zero suppression."""
    result = main(input_line)
    assert result.startswith("INTEREST=")
    value_part = result.split("=", 1)[1]
    # All characters must be digits or a single decimal point; no spaces.
    assert all(ch.isdigit() or ch == "." for ch in value_part)
    assert value_part.count(".") == 1
