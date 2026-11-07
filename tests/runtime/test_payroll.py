"""Payroll behavior checked through the real COBOL executable and shared harness."""

import json
from pathlib import Path
import random
import shutil
import subprocess
import sys

import pytest

import legacy
from legacy import runtime
import testing

ROOT = Path(__file__).resolve().parents[2]
INPUTS = json.loads((ROOT / "legacy/inputs/payroll.json").read_text())
REFERENCE_SOURCE = (ROOT / "tests/fixtures/payroll_reference.py").read_text()
reference_namespace = {}
exec(compile(REFERENCE_SOURCE, "payroll_reference.py", "exec"), reference_namespace)
reference_main = reference_namespace["main"]

# Handwritten checks, independent of the recording command and audit fixture.
EXPECTED = [
    "GROSS=0000700.00|TAX=0000090.00|NET=0000610.00",
    "GROSS=0000950.00|TAX=0000140.00|NET=0000810.00",
    "GROSS=0000999.75|TAX=0000149.95|NET=0000849.80",
    "GROSS=0001000.00|TAX=0000150.00|NET=0000850.00",
    "GROSS=0001000.38|TAX=0000150.11|NET=0000850.27",
    "GROSS=0000499.99|TAX=0000050.00|NET=0000449.99",
    "GROSS=0000500.00|TAX=0000050.00|NET=0000450.00",
    "GROSS=0000500.01|TAX=0000050.00|NET=0000450.01",
    "GROSS=0000000.00|TAX=0000000.00|NET=0000000.00",
    "GROSS=0000000.00|TAX=0000000.00|NET=0000000.00",
    "ERROR:INVALID_INPUT",
    "ERROR:INVALID_INPUT",
    "GROSS=1479970.20|TAX=0443841.06|NET=1036129.14",
    "ERROR:INVALID_INPUT",
    "GROSS=0000000.01|TAX=0000000.00|NET=0000000.01",
]


@pytest.fixture(scope="module")
def payroll_binary():
    return legacy.compile_cobol(ROOT / "legacy/payroll.cbl")


@pytest.mark.parametrize("input_line,expected", list(zip(INPUTS, EXPECTED)))
def test_original_payroll_cases(payroll_binary, input_line, expected):
    assert legacy.run_cobol(payroll_binary, input_line) == expected
    assert reference_main(input_line) == expected


@pytest.mark.parametrize("input_line", [
    "", "40", "40|", "|20", "40|20|", "40|1000.00", "40.001|20",
    "40|20.001", "4e1|20", "+40|20", "40|1,000", ".5|20", "40.|20",
    "40|2..0", "40|NaN", "40| 2 0", "0400|20",
])
def test_invalid_payroll_input(payroll_binary, input_line):
    assert legacy.run_cobol(payroll_binary, input_line) == "ERROR:INVALID_INPUT"


def test_spaces_and_leading_zeroes_are_supported(payroll_binary):
    assert legacy.run_cobol(payroll_binary, " 040.00 | 020.00 ") == (
        "GROSS=0000800.00|TAX=0000110.00|NET=0000690.00"
    )


def test_tax_uses_rounded_gross(payroll_binary):
    # Raw gross .0495 -> .05; tax is then .005 -> .01, not .00495 -> .00.
    assert legacy.run_cobol(payroll_binary, "0.01|4.95") == (
        "GROSS=0000000.05|TAX=0000000.01|NET=0000000.04"
    )


def test_payroll_decimal_audit(payroll_binary):
    # 30 grid cases + 7 targeted cases + 128 seeded cases = 165 extra audits.
    examples = [f"{hours}|{rate}"
                for hours in ("0", "0.01", "39.99", "40", "40.01", "999.99")
                for rate in ("0", "0.01", "12.50", "25", "999.99")]
    examples += ["1|499.99", "1|500", "1|500.01", "1|999.99",
                 "2|500", "1.01|990.11", "0.01|4.95"]
    generator = random.Random(202611079)
    for _ in range(128):
        hours = generator.randrange(100000)
        rate = generator.randrange(100000)
        examples.append(f"{hours // 100}.{hours % 100:02d}|{rate // 100}.{rate % 100:02d}")
    assert len(examples) == 165
    for line in examples:
        assert legacy.run_cobol(payroll_binary, line) == reference_main(line), line


def test_payroll_golden_schema_and_source_limit():
    cases = [json.loads(line) for line in (ROOT / "golden/payroll.jsonl").read_bytes().splitlines()]
    assert len(INPUTS) == len(EXPECTED) == len(cases) == 15
    assert len(set(INPUTS)) == 15
    assert cases == [{"input": line, "output": value} for line, value in zip(INPUTS, EXPECTED)]
    assert len((ROOT / "legacy/payroll.cbl").read_text().splitlines()) < 150


def test_record_payroll_uses_actual_original(payroll_binary, tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "GOLDEN_DIR", tmp_path / "golden")
    monkeypatch.chdir(tmp_path)
    destination = Path(legacy.record_golden("payroll", payroll_binary, INPUTS))
    assert destination.read_bytes() == (ROOT / "golden/payroll.jsonl").read_bytes()


@pytest.mark.parametrize("mutation", [None, "overtime", "flat_tax"])
def test_payroll_through_generated_equivalence_tests(tmp_path, monkeypatch, mutation):
    monkeypatch.setattr(testing, "TEST_DIR", tmp_path / "tests/equivalence")
    monkeypatch.setattr(testing, "REPORT_DIR", tmp_path / "reports")
    target = tmp_path / "payroll fixture.py"
    source = REFERENCE_SOURCE
    if mutation == "overtime":
        source = source.replace('OVERTIME_FACTOR = Decimal("1.5")',
                                'OVERTIME_FACTOR = Decimal("2")')
    elif mutation == "flat_tax":
        source = source.replace('    for width, percentage in TAX_SLICES:',
                                '    for width, percentage in ((None, Decimal("0.30")),):')
    target.write_text(source)
    testing.golden_to_pytest("payroll", target)
    result = testing.run_equivalence("payroll")
    assert result["total"] == 15
    if mutation is None:
        assert result == {"passed": 15, "total": 15, "failures": []}
    else:
        assert 0 < result["passed"] < 15
        failure = next(case for case in result["failures"] if case["input"] == "45.00|20.00")
        assert failure["expected"] == EXPECTED[1]
        if mutation == "overtime":
            assert failure["actual"] == "GROSS=0001000.00|TAX=0000150.00|NET=0000850.00"
        else:
            assert failure["actual"] == "GROSS=0000950.00|TAX=0000285.00|NET=0000665.00"


def test_payroll_cli_preserves_drifted_golden_and_supports_update(tmp_path):
    copy = tmp_path / "payroll handoff with spaces"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(
        ".git", "bin", "__pycache__", ".pytest_cache", ".venv", "validation", "runs",
    ))
    golden = copy / "golden/payroll.jsonl"
    original = golden.read_bytes()
    cases = [json.loads(line) for line in original.splitlines()]
    cases[0]["output"] = "incorrect reference"
    golden.write_text("".join(json.dumps(case) + "\n" for case in cases))
    modified = golden.read_bytes()
    def invoke(*arguments):
        return subprocess.run(
            [sys.executable, str(copy / "record_payroll.py"), *arguments],
            cwd=tmp_path, capture_output=True, text=True, timeout=30,
        )
    result = invoke("--check")
    assert result.returncode == 1 and "Case 1:" in result.stderr
    assert golden.read_bytes() == modified
    assert invoke().returncode == 1
    assert golden.read_bytes() == modified
    assert invoke("--update").returncode == 0
    assert golden.read_bytes() == original
    assert invoke("--check").returncode == 0
    golden.unlink()
    assert invoke("--check").returncode == 1
    assert not golden.exists()
    assert invoke().returncode == 0
    assert golden.read_bytes() == original
