import hashlib
import inspect
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import check_integration
import legacy
from legacy import runtime
import testing

ROOT = Path(__file__).resolve().parents[2]


def test_shared_contract_parameter_names():
    expected = [
        (legacy.compile_cobol, ["cobol_path"]),
        (legacy.run_cobol, ["binary_path", "input_line"]),
        (legacy.record_golden, ["module_id", "binary_path", "inputs"]),
        (testing.golden_to_pytest, ["module_id", "py_module_path"]),
        (testing.run_equivalence, ["module_id"]),
    ]
    for function, names in expected:
        assert list(inspect.signature(function).parameters) == names


def test_all_originals_and_quirk_via_cli_from_foreign_directory(tmp_path):
    goldens = [ROOT / f"golden/{module_id}.jsonl" for module_id in check_integration.MODULE_IDS]
    before = [hashlib.sha256(path.read_bytes()).digest() for path in goldens]
    destination = tmp_path / "smoke report.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "check_integration.py"), "--output", str(destination)],
        cwd=tmp_path, capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert json.loads(destination.read_text()) == report
    assert report["status"] == "passed" and report["passed"] == report["total"] == 45
    assert [item["module_id"] for item in report["modules"]] == ["interest", "payroll", "invoice"]
    assert all(item["passed"] == item["total"] == 15 for item in report["modules"])
    assert report["invoice_rounding_mutation"]["passed"] == 13
    assert len(report["invoice_rounding_mutation"]["failures"]) == 2
    assert report["invoice_after_restoring_truncation"] == {"passed": 15, "total": 15, "failures": []}
    assert [hashlib.sha256(path.read_bytes()).digest() for path in goldens] == before


def test_smoke_restores_private_paths_on_failure(tmp_path, monkeypatch):
    before = (runtime.GOLDEN_DIR, testing.GOLDEN_DIR, testing.TEST_DIR, testing.REPORT_DIR)
    monkeypatch.setattr(check_integration, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        check_integration.run_smoke()
    assert (runtime.GOLDEN_DIR, testing.GOLDEN_DIR, testing.TEST_DIR, testing.REPORT_DIR) == before


def test_smoke_rejects_original_golden_drift(tmp_path):
    copy = tmp_path / "team handoff"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(
        ".git", ".env", ".env.*", "bin", "__pycache__", ".pytest_cache", ".venv", "validation", "runs",
    ))
    golden = copy / "golden/interest.jsonl"
    cases = [json.loads(line) for line in golden.read_bytes().splitlines()]
    cases[0]["output"] = "fake reference"
    golden.write_text("".join(json.dumps(case) + "\n" for case in cases))
    changed = golden.read_bytes()
    destination = tmp_path / "must-not-exist.json"
    result = subprocess.run(
        [sys.executable, str(copy / "check_integration.py"), "--output", str(destination)],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1 and "Original/golden drift for interest" in result.stderr
    assert golden.read_bytes() == changed
    assert not destination.exists()
