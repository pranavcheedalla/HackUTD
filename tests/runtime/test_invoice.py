"""The original's real truncation, overflow, and generated equivalence tests."""

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
INPUTS = json.loads((ROOT / "legacy/inputs/invoice.json").read_text())
REFERENCE_SOURCE = (ROOT / "tests/fixtures/invoice_reference.py").read_text()
namespace = {}
exec(compile(REFERENCE_SOURCE, "invoice_reference.py", "exec"), namespace)
reference_main = namespace["main"]
EXPECTED = [
    "TOTAL=00053.97", "TOTAL=00012.34", "TOTAL=00000.00", "TOTAL=99999.99",
    "TOTAL=99900.00", "ERROR:OVERFLOW", "TOTAL=00000.00", "TOTAL=00000.00",
    "TOTAL=00059.97", "TOTAL=00000.00", "ERROR:INVALID_INPUT",
    "ERROR:INVALID_INPUT", "ERROR:INVALID_INPUT", "ERROR:INVALID_INPUT", "TOTAL=00000.00",
]


@pytest.fixture(scope="module")
def invoice_binary():
    return legacy.compile_cobol(ROOT / "legacy/invoice.cbl")


@pytest.mark.parametrize("input_line,expected", list(zip(INPUTS, EXPECTED)))
def test_original_invoice_cases(invoice_binary, input_line, expected):
    assert legacy.run_cobol(invoice_binary, input_line) == expected
    assert reference_main(input_line) == expected


@pytest.mark.parametrize("input_line", [
    "", "1|10", "1||10", "|10|0", "1|10|", "1|10|0|", "1.0|10|0",
    "1000|10|0", "1|100000.00|0", "1|10|1000", "1|10.001|0",
    "1|10|0.001", "1|10|-0", "+1|10|0", "1e1|10|0", "1|NaN|0",
    "1|.5|0", "1|10.|0", "1|1,000|0", "1|1..0|0",
])
def test_invalid_invoice_inputs(invoice_binary, input_line):
    assert legacy.run_cobol(invoice_binary, input_line) == "ERROR:INVALID_INPUT"


def test_spaces_and_zeroes(invoice_binary):
    assert legacy.run_cobol(invoice_binary, " 001 | 00012.35 | 000.01 ") == "TOTAL=00012.34"


def test_fractional_cents_at_capacity_are_truncated_not_rejected(invoice_binary):
    # Exact 99999.996 fits after truncation. Rounding would overflow to 100000.
    assert legacy.run_cobol(invoice_binary, "2|99980.00|49.99") == "TOTAL=99999.99"


def test_invoice_decimal_audit(invoice_binary):
    examples = [f"{quantity}|{price}|{discount}"
                for quantity in ("0", "1", "2", "3", "999")
                for price in ("0", "0.01", "12.35", "50000", "99999.99")
                for discount in ("0", "0.01", "50", "100")]
    examples += ["3|37037.04|10", "3|37037.03|10", "1|0.05|10",
                 "1|0.06|10", "2|55555.55|10", "1|12.35|0.01", "2|99980.00|49.99"]
    generator = random.Random(2026110710)
    for _ in range(128):
        quantity = generator.randrange(1000)
        price = generator.randrange(10000000)
        discount = generator.randrange(10001)
        examples.append(f"{quantity}|{price // 100}.{price % 100:02d}|{discount // 100}.{discount % 100:02d}")
    assert len(examples) == 235
    for line in examples:
        assert legacy.run_cobol(invoice_binary, line) == reference_main(line), line


def test_invoice_golden_and_source_contract():
    cases = [json.loads(line) for line in (ROOT / "golden/invoice.jsonl").read_bytes().splitlines()]
    assert len(INPUTS) == len(EXPECTED) == len(cases) == len(set(INPUTS)) == 15
    assert cases == [{"input": line, "output": value} for line, value in zip(INPUTS, EXPECTED)]
    source = (ROOT / "legacy/invoice.cbl").read_text()
    assert len(source.splitlines()) < 150
    assert "PIC 9(5)V99" in source


def test_record_invoice_executes_the_original(invoice_binary, tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "GOLDEN_DIR", tmp_path / "golden")
    monkeypatch.chdir(tmp_path)
    path = Path(legacy.record_golden("invoice", invoice_binary, INPUTS))
    assert path.read_bytes() == (ROOT / "golden/invoice.jsonl").read_bytes()


def test_rounding_divergence_and_repair_through_shared_harness(tmp_path, monkeypatch):
    monkeypatch.setattr(testing, "TEST_DIR", tmp_path / "tests/equivalence")
    monkeypatch.setattr(testing, "REPORT_DIR", tmp_path / "reports")
    target = tmp_path / "invoice fixture.py"
    target.write_text(REFERENCE_SOURCE)
    testing.golden_to_pytest("invoice", target)
    assert testing.run_equivalence("invoice") == {"passed": 15, "total": 15, "failures": []}
    target.write_text(REFERENCE_SOURCE.replace("ROUND_DOWN", "ROUND_HALF_UP"))
    result = testing.run_equivalence("invoice")
    assert result == {"passed": 13, "total": 15, "failures": [
        {"input": "1|12.35|0.01", "expected": "TOTAL=00012.34", "actual": "TOTAL=00012.35"},
        {"input": "1|0.01|50.00", "expected": "TOTAL=00000.00", "actual": "TOTAL=00000.01"},
    ]}
    target.write_text(REFERENCE_SOURCE)
    assert testing.run_equivalence("invoice")["passed"] == 15


def test_invoice_cli_drift_update_and_relocation(tmp_path):
    copy = tmp_path / "invoice handoff with spaces"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(
        ".git", ".env", ".env.*", "bin", "__pycache__", ".pytest_cache", ".venv", "validation", "runs",
    ))
    golden = copy / "golden/invoice.jsonl"
    original = golden.read_bytes()
    cases = [json.loads(line) for line in original.splitlines()]
    cases[1]["output"] = "TOTAL=00012.35"
    golden.write_text("".join(json.dumps(case) + "\n" for case in cases))
    modified = golden.read_bytes()
    def invoke(*arguments):
        return subprocess.run([sys.executable, str(copy / "record_invoice.py"), *arguments],
                              cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert invoke("--check").returncode == 1
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
