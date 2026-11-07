"""P3 (Abhinav): understand() returns link/copy_dirs/kind/params; make_driver(); driver-format inputs."""
import importlib
import subprocess

import pytest

import agents
from agents.cobol_static import analyze, render_summary
from cbhelpers import INPUTS, SAMPLES, call_or_pending, needs_cobc, pending, reference, run_binary

OWNER = "P3 Abhinav, agents/understand.py + cobol_static.py + driver.py"
DISCOUNT_PARAMS = [
    {"name": "LK-TIER", "pic": "X", "kind": "text", "int_digits": 0, "dec_digits": 0, "length": 1, "signed": False},
    {"name": "LK-SUBTOTAL", "pic": "9(7)V99", "kind": "numeric", "int_digits": 7, "dec_digits": 2, "length": 9,
     "signed": False},
    {"name": "LK-RATE", "pic": "9(2)V99", "kind": "numeric", "int_digits": 2, "dec_digits": 2, "length": 4,
     "signed": False},
]


@pytest.fixture(scope="module")
def modules():
    found = {m["module_id"]: m for m in agents.understand(str(SAMPLES))}
    if "kind" not in found["discount"]:
        pending(OWNER, "understand() does not return kind/link/copy_dirs/params yet")
    return found


def test_dependency_order_callees_first():
    order = [m["module_id"] for m in agents.understand(str(SAMPLES))]
    assert order.index("discount") < order.index("invoice")


def test_invoice_links_discount_and_finds_copybook_dir(modules):
    invoice = modules["invoice"]
    assert invoice["kind"] == "program"
    assert invoice["depends_on"] == ["discount"]
    assert invoice["link"] == [str((SAMPLES / "discount.cbl").resolve())]
    assert invoice["copy_dirs"] == [str((SAMPLES / "copybooks").resolve())]
    assert invoice["params"] == []


def test_discount_is_a_subprogram_with_params(modules):
    discount = modules["discount"]
    assert discount["kind"] == "subprogram"
    assert discount["link"] == [] and discount["depends_on"] == []
    assert discount["params"] == DISCOUNT_PARAMS


def test_standalone_program_has_no_links(modules):
    assert modules["interest"]["kind"] == "program" and modules["interest"]["link"] == []


def test_static_summary_describes_driver_input_line():
    summary = render_summary(analyze((SAMPLES / "discount.cbl").read_text()))
    if "LK-TIER|LK-SUBTOTAL|LK-RATE" not in summary:
        pending(OWNER, "render_summary must state the driver input line LK-TIER|LK-SUBTOTAL|LK-RATE")


@needs_cobc
def test_make_driver_matches_reference_on_every_input(tmp_path):
    driver = call_or_pending(OWNER, agents.make_driver, (SAMPLES / "discount.cbl").read_text())
    assert "PROGRAM-ID. DRV-DISCOUNT" in driver.upper()
    (tmp_path / "drv.cbl").write_text(driver)
    # Plain cobc, so this test does not depend on P2's compile_program.
    subprocess.run(["cobc", "-c", "-fixed", "-o", str(tmp_path / "discount.o"), str(SAMPLES / "discount.cbl")],
                   check=True)
    subprocess.run(["cobc", "-x", "-free", "-o", str(tmp_path / "drv"), str(tmp_path / "drv.cbl"),
                    str(tmp_path / "discount.o")], check=True, capture_output=True)
    ref = reference("discount")
    for line in INPUTS["discount"]:
        assert run_binary(str(tmp_path / "drv"), line) == ref.main(line), line


def test_generate_inputs_keeps_driver_format_for_subprograms(monkeypatch):
    if "LK-TIER|LK-SUBTOTAL|LK-RATE" not in render_summary(analyze((SAMPLES / "discount.cbl").read_text())):
        pending(OWNER, "driver-format input support")
    gi = importlib.import_module("agents.generate_inputs")
    proposals = [f"{t}|{s}.00|0" for t in "GSX" for s in (1, 999, 1000, 1001, 5000, 99999, 9999999)]
    monkeypatch.setattr(gi._llm, "call_llm", lambda *a, **k: {"cases": [{"input": p, "covers": "x"} for p in proposals]})
    lines = gi.generate_inputs({"module_id": "discount"}, (SAMPLES / "discount.cbl").read_text())
    assert 20 <= len(lines) <= 30
    assert all(line.count("|") == 2 for line in lines)
