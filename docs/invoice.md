# Segment 10: invoice and the real truncation quirk

Module ID: `invoice`. Source: `legacy/invoice.cbl` (101 lines).
Inputs: `legacy/inputs/invoice.json`. Reference: `golden/invoice.jsonl`.
There are no CALL/COPY dependencies or file/database operations in the original.

## Exact behavior

The program reads one line: `quantity|unit_price|discount_percent`.

| Field | Valid range | Syntax | Storage |
| --- | --- | --- | --- |
| Quantity | 0–999 | 1–3 digits, no decimal point | `PIC 9(3)` |
| Unit price | 0–99999.99 | 1–5 integer digits, optional 1–2 fractional digits | `PIC 9(5)V99` |
| Discount percent | 0–100.00 | 1–3 integer digits, optional 1–2 fractional digits | `PIC 9(3)V99` |

Exactly two `|` separators are required. ASCII spaces around fields and leading
zeros within field digit limits are accepted. Signs, negative values, exponent
notation, grouping commas, empty fields, extra digits, and extra separators
produce `ERROR:INVALID_INPUT`. The supported line fits the 256-character ACCEPT
buffer. Discount is explicitly supplied; the program does not choose a tier.

Calculation order:

1. Calculate `quantity * unit_price * (100 - discount_percent) / 100` in a wide
   `PIC 9(8)V9(6)` field. This preserves all six possible fractional digits for
   the accepted inputs, including the maximum subtotal before discount.
2. If this exact total is at least 100000, print `ERROR:OVERFLOW`.
3. **MOVE the exact total into `PIC 9(5)V99`.** COBOL discards the extra
   fractional digits. There is no rounding or warning for fractional cents.
4. Print `TOTAL=` followed by five integer digits, a dot, and two decimal digits.

The final DISPLAY newline is removed by `legacy.run_cobol`. Successful returned
strings contain no spaces, currency symbol, or trailing newline.

## The demo divergence

```text
Input: 1|12.35|0.01
Exact total: 12.348765
Original COBOL: TOTAL=00012.34
Incorrect rounding rewrite: TOTAL=00012.35
```

A second revealing case is `1|0.01|50.00`: exact `.005` becomes `TOTAL=00000.00`,
where rounding half-up would produce `TOTAL=00000.01`.

This is an actual COBOL numeric-field conversion, not an answer fabricated by
the recorder. Preserving it is required for equivalence even if rounding would
be preferred in a newly designed billing system.

Fractional truncation and integer overflow are distinct. In an additional audit
case, `2|99980.00|49.99` gives `99999.996`, which fits after truncation and must
return `TOTAL=99999.99`. Rejecting any exact value above `99999.99` would be wrong.

## Fifteen handwritten inputs and recorded outputs

| # | Input | Purpose | Exact recorded output |
| --- | --- | --- | --- |
| 1 | `3\|19.99\|10.00` | Ordinary discounted invoice | `TOTAL=00053.97` |
| 2 | `1\|12.35\|0.01` | Truncation differs from rounding | `TOTAL=00012.34` |
| 3 | `1\|0.01\|50.00` | Half-cent truncates to zero | `TOTAL=00000.00` |
| 4 | `1\|99999.99\|0.00` | Maximum unit price and final field | `TOTAL=99999.99` |
| 5 | `999\|100.00\|0.00` | Maximum quantity, valid total | `TOTAL=99900.00` |
| 6 | `2\|50000.00\|0.00` | Integer overflow boundary | `ERROR:OVERFLOW` |
| 7 | `0\|19.99\|10.00` | Zero quantity | `TOTAL=00000.00` |
| 8 | `3\|0.00\|10.00` | Zero price | `TOTAL=00000.00` |
| 9 | `3\|19.99\|0.00` | No discount | `TOTAL=00059.97` |
| 10 | `3\|19.99\|100.00` | Full discount | `TOTAL=00000.00` |
| 11 | `-1\|19.99\|10.00` | Negative quantity | `ERROR:INVALID_INPUT` |
| 12 | `1\|-19.99\|10.00` | Negative price | `ERROR:INVALID_INPUT` |
| 13 | `1\|19.99\|-1.00` | Negative discount | `ERROR:INVALID_INPUT` |
| 14 | `1\|19.99\|100.01` | Discount exceeds 100% | `ERROR:INVALID_INPUT` |
| 15 | `999\|99999.99\|100.00` | All maximum inputs; wide intermediate | `TOTAL=00000.00` |

All golden answers were recorded by executing the original. The independent
Python fixture never supplies the recorder's answers.

## Reproduce and hand off

```bash
python record_invoice.py --check
python -m pytest -q tests/runtime/test_invoice.py
python check_integration.py --output runs/person2-smoke.json
```

The recorder creates a missing file or verifies an existing file without
changing it. Use `--update` for a deliberate re-record after reviewing changes.
All commands work by absolute script path from a different working directory.

After Person 4 writes `modern/invoice.py`, the shared pipeline calls:

```python
import testing

testing.golden_to_pytest("invoice", "modern/invoice.py")
result = testing.run_equivalence("invoice")
```

Use `decimal.Decimal` and explicit truncation (`ROUND_DOWN` for nonnegative
values). Include validation and overflow responses as part of equivalence.
The fixture under `tests/fixtures/` is audit code, not the agent-generated rewrite.

## Checks

The tests cover the 15 recorded cases, invalid syntax, input/amount boundaries,
and 235 additional Decimal audits (100 grid examples, seven targeted examples,
128 seeded examples). The shared pytest runner verifies the correct fixture,
detects two differences after changing truncation to half-up rounding, then
passes all 15 again after restoring truncation. The smoke command extends that
sequence across all three originals. It does not run Nemotron or LangGraph.
