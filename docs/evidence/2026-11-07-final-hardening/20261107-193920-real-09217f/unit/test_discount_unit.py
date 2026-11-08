import pytest
from decimal import Decimal
from modern.discount import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rate_only(output: str) -> str:
    """Extract the LK-RATE=... portion from main() output."""
    for chunk in output.split("|"):
        if chunk.startswith("LK-RATE="):
            return chunk
    raise AssertionError(f"output missing LK-RATE: {output!r}")


def _subtotal_only(output: str) -> str:
    """Extract the LK-SUBTOTAL=... portion from main() output."""
    for chunk in output.split("|"):
        if chunk.startswith("LK-SUBTOTAL="):
            return chunk
    raise AssertionError(f"output missing LK-SUBTOTAL: {output!r}")


def _tier_only(output: str) -> str:
    """Extract the LK-TIER=... portion from main() output."""
    for chunk in output.split("|"):
        if chunk.startswith("LK-TIER="):
            return chunk
    raise AssertionError(f"output missing LK-TIER: {output!r}")


# ---------------------------------------------------------------------------
# Boundary / equivalence partition tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "|",                       # blank / missing everything
        "||",                      # three empty tokens
        "|0|",                     # zero subtotal, empty rate
        "|9999999.99|",            # max subtotal (all 9s)
        "|0.01|",                  # smallest non-zero subtotal
        "|99.99|",                 # max rate field size
        "|0.01|",                  # smallest non-zero rate
        "|999999999.99|",          # extra-long subtotal (high-order digits dropped)
        "|999.99|",                # extra-long rate (high-order digits dropped)
        "G|2000.00|",              # tier G overrides subtotal
        "S|1000.00|",              # tier S overrides subtotal threshold
        "X|500.00|",               # no tier match, below threshold
        "|1500.00|",               # empty tier, subtotal >= 1000
        "A|999.99|",               # below threshold, other branch
        "g|1500.00|",              # lowercase g is NOT tier G (case-sensitive)
        "s|1500.00|",              # lowercase s is NOT tier S (case-sensitive)
        "AB|1500.00|",             # tier cut to first char 'A'
    ],
)
def test_main_never_raises_and_returns_str(input_line):
    """main() must never raise and must always return a str for any input."""
    result = main(input_line)
    assert isinstance(result, str)


@pytest.mark.parametrize(
    "input_line",
    [
        "|",                       # blank input
        "||",                      # three empty tokens
        "|0|",                     # zero subtotal
        "|9999999.99|",            # max subtotal
        "|0.01|",                  # smallest non-zero subtotal
        "|99.99|",                 # max rate
        "|0.01|",                  # smallest non-zero rate
        "|999999999.99|",          # extra-long subtotal
        "|999.99|",                # extra-long rate
        "G|2000.00|",
        "S|1000.00|",
        "X|500.00|",
        "|1500.00|",
        "A|999.99|",
        "g|1500.00|",
        "s|1500.00|",
        "AB|1500.00|",
    ],
)
def test_main_deterministic(input_line):
    """Same input must always produce the same output."""
    assert main(input_line) == main(input_line)


@pytest.mark.parametrize(
    "input_line",
    [
        "|",
        "||",
        "|0|",
        "|9999999.99|",
        "|0.01|",
        "|99.99|",
        "|0.01|",
        "|999999999.99|",
        "|999.99|",
        "G|2000.00|",
        "S|1000.00|",
        "X|500.00|",
        "|1500.00|",
        "A|999.99|",
        "g|1500.00|",
        "s|1500.00|",
        "AB|1500.00|",
    ],
)
def test_output_fixed_width_length_stable(input_line):
    """Every output line must keep the same total length across all inputs."""
    result = main(input_line)
    assert len(result) == len(main("|")), (
        f"output length changed for {input_line!r}: "
        f"{len(result)} != {len(main('|'))}"
    )


# ---------------------------------------------------------------------------
# Exact output values (computable with certainty from the spec)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line, expected_rate",
    [
        # Spec edge cases
        ("G|2000.00|", "12.50"),   # first WHEN TRUE branch taken
        ("X|500.00|", "00.00"),    # no tier match, below threshold
        ("S|1000.00|", "07.25"),   # tier match before subtotal comparison
        ("|1500.00|", "05.00"),    # empty tier, subtotal >= 1000
        ("A|999.99|", "00.00"),    # below threshold, other branch
        # Business rules
        ("G|0|", "12.50"),         # tier G always wins
        ("S|0|", "07.25"),         # tier S always wins
        ("|1000.00|", "05.00"),    # subtotal exactly at threshold
        ("|999.99|", "00.00"),     # subtotal just below threshold
        ("|0|", "00.00"),          # zero subtotal -> other branch
        # Case sensitivity
        ("g|1500.00|", "05.00"),   # lowercase g not matched
        ("s|1500.00|", "05.00"),   # lowercase s not matched
        # Tier field cut to one char
        ("AB|1500.00|", "05.00"),  # 'A' -> not G/S, subtotal branch
    ],
)
def test_main_exact_rate_values(input_line, expected_rate):
    """Exact rate outputs are certain from the spec business rules.

    LK-RATE is PIC 9(2)V99, so display_num zero-pads the integer part to
    exactly 2 digits: 12.50 -> "12.50", 7.25 -> "07.25", 5.00 -> "05.00",
    0.00 -> "00.00".
    """
    assert _rate_only(main(input_line)) == f"LK-RATE={expected_rate}"


# ---------------------------------------------------------------------------
# Monotonic rules implied by the spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "low_subtotal, high_subtotal",
    [
        ("0", "999.99"),           # both below threshold -> same rate
        ("1000.00", "9999999.99"), # both at/above threshold -> same rate
    ],
)
def test_main_subtotal_monotonic_rate_below_threshold(low_subtotal, high_subtotal):
    """Within the same subtotal branch, raising subtotal never lowers the rate."""
    low_rate = Decimal(_rate_only(main(f"|{low_subtotal}|")).split("=")[1])
    high_rate = Decimal(_rate_only(main(f"|{high_subtotal}|")).split("=")[1])
    assert high_rate >= low_rate


@pytest.mark.parametrize(
    "low_rate, high_rate",
    [
        ("0", "99.99"),            # rate input field: larger stored value
    ],
)
def test_main_input_rate_ignored_for_output(low_rate, high_rate):
    """The input LK-RATE is overwritten by the business rules; output must not
    depend on the input rate value when a tier/subtotal branch fires."""
    # With tier G, output rate is always 12.50 regardless of input rate.
    out_low = _rate_only(main(f"G|0|{low_rate}"))
    out_high = _rate_only(main(f"G|0|{high_rate}"))
    assert out_low == out_high == "LK-RATE=12.50"


# ---------------------------------------------------------------------------
# Error / validation branch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "|abc|",                   # non-numeric subtotal -> NUMVAL returns 0
        "|1.2.3|",                 # malformed number -> NUMVAL returns 0
        "|-5.00|",                 # negative subtotal -> unsigned field drops sign
        "|abc|99.99|",             # non-numeric subtotal, valid rate
    ],
)
def test_main_invalid_numeric_input_does_not_crash(input_line):
    """Invalid numeric text must be handled gracefully (NUMVAL -> 0), not raise."""
    result = main(input_line)
    assert isinstance(result, str)
    assert "LK-RATE=" in result


# ---------------------------------------------------------------------------
# Output format properties
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "|",
        "G|2000.00|",
        "S|1000.00|",
        "X|500.00|",
        "|1500.00|",
        "A|999.99|",
    ],
)
def test_main_rate_output_has_two_decimal_places(input_line):
    """LK-RATE is PIC 9(2)V99, displayed with exactly two implied decimals."""
    rate_part = _rate_only(main(input_line))
    value = rate_part.split("=")[1]
    assert value.count(".") == 1
    int_part, dec_part = value.split(".")
    assert len(dec_part) == 2
    assert len(int_part) == 2  # zero-padded to 2 integer digits


@pytest.mark.parametrize(
    "input_line",
    [
        "|",
        "G|2000.00|",
        "X|9999999.99|",
    ],
)
def test_main_subtotal_output_has_two_decimal_places(input_line):
    """LK-SUBTOTAL is PIC 9(7)V99, displayed with exactly two implied decimals."""
    sub_part = _subtotal_only(main(input_line))
    value = sub_part.split("=")[1]
    assert value.count(".") == 1
    int_part, dec_part = value.split(".")
    assert len(dec_part) == 2
    assert len(int_part) == 7  # zero-padded to 7 integer digits


@pytest.mark.parametrize(
    "input_line",
    [
        "|",
        "G|2000.00|",
        "X|500.00|",
    ],
)
def test_main_tier_output_is_single_character(input_line):
    """LK-TIER is PIC X, exactly one character (space-padded if blank)."""
    tier_part = _tier_only(main(input_line))
    value = tier_part.split("=")[1]
    assert len(value) == 1


# ---------------------------------------------------------------------------
# Output line structure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_line",
    [
        "|",
        "G|2000.00|",
        "X|500.00|",
    ],
)
def test_main_output_contains_all_three_fields(input_line):
    """Output must always contain LK-TIER, LK-SUBTOTAL, and LK-RATE in order."""
    result = main(input_line)
    assert result.startswith("LK-TIER=")
    assert "|LK-SUBTOTAL=" in result
    assert "|LK-RATE=" in result
    # Exactly two separators -> three fields
    assert result.count("|") == 2
