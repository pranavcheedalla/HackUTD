# Segment 9: payroll original and golden cases

Module ID: `payroll`. Source: `legacy/payroll.cbl` (104 lines).
Inputs: `legacy/inputs/payroll.json`. Reference: `golden/payroll.jsonl`.
There are no CALL/COPY dependencies, files, databases, or model calls.

## Business rules to extract and preserve

This sample defines fictional weekly-pay and tax rules for the hackathon:

1. Read one line in the form `hours|hourly_rate`. Validate both fields before
   moving them into unsigned numeric storage.
2. Pay up to 40 hours at the hourly rate. Pay only the hours above 40 at 1.5x.
3. Combine regular and overtime earnings, then round gross pay once to cents.
4. Calculate progressive tax using the **rounded gross**:
   - First $500: 10%.
   - Next $500: 20%.
   - Portion above $1,000: 30%.
5. Round the combined tax to cents. Net pay is rounded gross minus rounded tax.
6. Print the three amounts in the exact format below.

Both rounding operations are COBOL `ROUNDED`, which is half-up for these
nonnegative values. This program intentionally rounds; the invoice sample will
later demonstrate truncation. Rates are decimal constants, not floating-point
approximations in the Python audit fixture.

Example with 45 hours at $20:

```text
regular = 40 × 20 = 800
overtime = 5 × 20 × 1.5 = 150
gross = 950.00
tax = 500 × 10% + 450 × 20% = 140.00
net = 810.00
```

Input and exact output:

```text
45.00|20.00
GROSS=0000950.00|TAX=0000140.00|NET=0000810.00
```

## Accepted format and fields

| Field | Valid range | Syntax | COBOL storage |
| --- | --- | --- | --- |
| Hours | 0–999.99 inclusive | 1–3 integer digits, optional dot and 1–2 fractional digits | `PIC 9(3)V99` |
| Hourly rate | 0–999.99 inclusive | Same | `PIC 9(3)V99` |
| Each output amount | 0–9999999.99 | Seven integer digits, dot, two fractional digits | `PIC 9(7)V99`, displayed through `PIC 9(7).99` |

Exactly one `|` is required. ASCII spaces around fields and leading zeroes
within the digit limits are accepted. Negative values, a plus sign, exponent
notation, grouping commas, empty fields, extra separators, and extra digits
are invalid. The line must fit the 256-character ACCEPT buffer; longer lines
are outside the supported format. Hours above 40 are allowed up to the field
maximum, so maximum-field tests exercise the arithmetic as requested.

Invalid input prints `ERROR:INVALID_INPUT` and exits normally. That response is
a valid golden outcome. An arithmetic size-error guard prints `ERROR:OVERFLOW`;
all valid combinations fit the output fields, so that guard is defensive.

The maximum valid input `999.99|999.99` produces gross `1479970.20`, tax
`0443841.06`, and net `1036129.14`. There is no currency symbol, extra space,
or sign in successful output. One final DISPLAY newline is removed by
`legacy.run_cobol`; the recorded/returned string has no final newline.

## Fifteen handwritten inputs

Amounts below are readable dollar values; JSONL preserves the exact padded strings.

| # | Input | Purpose | Gross | Tax | Net |
| --- | --- | --- | --- | --- | --- |
| 1 | `35.00\|20.00` | Regular pay; middle tax band | 700.00 | 90.00 | 610.00 |
| 2 | `45.00\|20.00` | Overtime at 1.5x | 950.00 | 140.00 | 810.00 |
| 3 | `39.99\|25.00` | Just below overtime and below upper tax boundary | 999.75 | 149.95 | 849.80 |
| 4 | `40.00\|25.00` | Exactly 40 hours and $1,000 gross | 1000.00 | 150.00 | 850.00 |
| 5 | `40.01\|25.00` | Just above overtime and $1,000 | 1000.38 | 150.11 | 850.27 |
| 6 | `1.00\|499.99` | Below $500 boundary; tax rounding | 499.99 | 50.00 | 449.99 |
| 7 | `1.00\|500.00` | Exactly $500 gross | 500.00 | 50.00 | 450.00 |
| 8 | `1.00\|500.01` | One cent above $500 | 500.01 | 50.00 | 450.01 |
| 9 | `0.00\|20.00` | Zero hours | 0.00 | 0.00 | 0.00 |
| 10 | `40.00\|0.00` | Zero rate | 0.00 | 0.00 | 0.00 |
| 11 | `-1.00\|20.00` | Negative hours | ERROR:INVALID_INPUT | — | — |
| 12 | `40.00\|-1.00` | Negative rate | ERROR:INVALID_INPUT | — | — |
| 13 | `999.99\|999.99` | Maximum value in both input fields | 1479970.20 | 443841.06 | 1036129.14 |
| 14 | `1000.00\|20.00` | Hours exceed field width | ERROR:INVALID_INPUT | — | — |
| 15 | `0.50\|0.01` | Half-cent gross rounds upward | 0.01 | 0.00 | 0.01 |

These outputs were obtained by executing COBOL. The production recorder does
not use the Python fixture or these documented values to create answers.

## Reproduce and verify

From the repository root, with the Python 3.11 environment active:

```bash
python record_payroll.py --check
python -m pytest -q tests/runtime/test_payroll.py
python -m pytest -q
```

`record_payroll.py` creates a missing golden file or verifies an existing one.
It never silently replaces a differing reference. Use `--update` only after
reviewing deliberate source/input changes. The script also works when invoked
by absolute path from a different working directory.

Shared runtime calls, which do not require the script:

```python
import json
from pathlib import Path
import legacy

root = Path.cwd()
binary = legacy.compile_cobol(root / "legacy/payroll.cbl")
result = legacy.run_cobol(binary, "45.00|20.00")
inputs = json.loads((root / "legacy/inputs/payroll.json").read_text())
golden_path = legacy.record_golden("payroll", binary, inputs)
```

After Person 4 creates the real rewrite, the existing shared harness works
without a signature change:

```python
import testing

testing.golden_to_pytest("payroll", "modern/payroll.py")
result = testing.run_equivalence("payroll")
# Matching implementation: {"passed": 15, "total": 15, "failures": []}
```

Test generation can happen before the rewrite exists; running it follows the
rewrite phase. We do not commit generated tests pointing at an absent rewrite.

## Validation beyond the fifteen recordings

`tests/fixtures/payroll_reference.py` is an independent handwritten Decimal
audit fixture. It accumulates tax by slices instead of copying COBOL's
piecewise formulas. It is not the model's rewrite and is never used to record
golden outputs.

- All 15 original cases are checked against handwritten expectations.
- 165 additional examples compare actual COBOL with Decimal: 30 boundary-grid
  examples, seven targeted examples, and 128 seeded examples.
- An extra ordering check uses `0.01|4.95`: raw gross `.0495` rounds to `.05`,
  tax then rounds from `.005` to `.01`, leaving net `.04`. Taxing unrounded
  gross would incorrectly produce zero tax.
- The correct handwritten fixture passes all 15 cases through the real
  generated-pytest/equivalence-runner path.
- Two intentionally wrong fixtures (double-time and flat 30% tax) produce
  structured failures containing exact input, expected, and actual strings.
- Malformed inputs, field limits, spaces, zero padding, recording reproducibility,
  and the CLI's drift/update behavior are covered.

Passing this finite set establishes tested behavior, not equivalence for every
possible input. The full model/orchestration integration remains Hemant's step.
