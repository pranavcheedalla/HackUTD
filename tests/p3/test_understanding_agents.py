"""Offline tests for P3's agents (no API key). Run: pytest tests/unit -q"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

import agents  # noqa: E402,F401  (agents/__init__ re-exports functions with the same names as modules)
from agents import _llm  # noqa: E402
from agents._json import extract_json  # noqa: E402

es, gi = sys.modules["agents.extract_spec"], sys.modules["agents.generate_inputs"]
from agents.cobol_static import analyze  # noqa: E402
from agents.understand import load_cobol_source, understand  # noqa: E402
from fake_llm import fake_call_llm  # noqa: E402

SAMPLES = ROOT / "samples" / "legacy"
_extract_spec, _generate_inputs = es.extract_spec, gi.generate_inputs


@pytest.fixture
def invoice_src():
    return load_cobol_source(SAMPLES / "invoice.cbl")


# ---------------------------------------------------------------- understand
def test_understand_orders_leaves_first():
    mods = understand(SAMPLES)
    ids = [m["module_id"] for m in mods]
    assert ids.index("discount") < ids.index("invoice")
    inv = next(m for m in mods if m["module_id"] == "invoice")
    assert inv["depends_on"] == ["discount"]
    assert inv["copybooks"][0].endswith("INVREC.cpy")
    assert {"module_id", "cobol_path", "depends_on"} <= set(inv)


def test_understand_ignores_calls_in_comments_and_literals(tmp_path):
    (tmp_path / "a.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. A.\n"
        "      * CALL 'B' in a comment\n       PROCEDURE DIVISION.\n"
        "           DISPLAY \"CALL 'B'\"\n           CALL 'C'\n           STOP RUN.\n")
    (tmp_path / "b.cbl").write_text("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. B.\n")
    (tmp_path / "c.cbl").write_text("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. C.\n")
    mods = {m["module_id"]: m for m in understand(tmp_path)}
    assert mods["a"]["depends_on"] == ["c"]


def test_understand_survives_cycles(tmp_path):
    for me, other in (("x", "Y"), ("y", "X")):
        (tmp_path / f"{me}.cbl").write_text(
            f"       PROGRAM-ID. {me.upper()}.\n       PROCEDURE DIVISION.\n           CALL '{other}'.\n")
    assert sorted(m["module_id"] for m in understand(tmp_path)) == ["x", "y"]


def test_copybook_expanded(invoice_src):
    assert "INV-UNIT-PRICE" in invoice_src
    assert "\n       COPY INVREC." not in invoice_src  # the statement itself is gone (marker comment stays)


# ---------------------------------------------------------------- static analysis
def test_input_layout_and_truncation(invoice_src):
    a = analyze(invoice_src)
    assert a.input_width == 12
    assert [(f["name"], f["start"], f["end"]) for f in a.input_layout] == [
        ("INV-QTY", 1, 4), ("INV-UNIT-PRICE", 5, 11), ("INV-CUST-TIER", 12, 12)]
    assert a.truncation_targets == ["WS-DISC-AMT"]  # ROUNDED/SIZE ERROR statements are not flagged


def test_rounded_compute_not_flagged():
    a = analyze((SAMPLES / "interest.cbl").read_text())
    assert a.input_width == 15 and a.truncation_targets == []


# ---------------------------------------------------------------- extract_spec
def test_extract_spec_valid_and_static_quirk_added(monkeypatch, invoice_src):
    monkeypatch.setattr(_llm, "call_llm", fake_call_llm)
    spec = _extract_spec(invoice_src)
    assert es.validate_spec(spec) == []
    assert spec["module_id"] == "invoice"
    assert any("WS-DISC-AMT" in q and "TRUNCATED" in q for q in spec["quirks"])


def test_extract_spec_no_duplicate_quirk_when_model_found_it(monkeypatch, invoice_src):
    def llm(model, system, user, schema=None):
        r = fake_call_llm(model, system, user, schema)
        r["quirks"] = ["WS-DISC-AMT PIC 9(5)V99 truncates fractions of a cent instead of rounding"]
        return r

    monkeypatch.setattr(_llm, "call_llm", llm)
    assert len(_extract_spec(invoice_src)["quirks"]) == 1


def test_extract_spec_retries_once_with_errors(monkeypatch, invoice_src):
    calls = []

    def llm(model, system, user, schema=None):
        calls.append(user)
        if len(calls) == 1:
            return '```json\n{"summary": "x", "inputs": "oops"}\n```'
        return fake_call_llm(model, system, user, schema)

    monkeypatch.setattr(_llm, "call_llm", llm)
    spec = _extract_spec(invoice_src)
    assert len(calls) == 2 and "did not match the required schema" in calls[1]
    assert es.validate_spec(spec) == []


def test_extract_spec_never_crashes_on_garbage(monkeypatch, invoice_src):
    monkeypatch.setattr(_llm, "call_llm", lambda *a, **k: "I cannot help with that")
    spec = _extract_spec(invoice_src)
    assert es.validate_spec(spec) == []
    assert [i["name"] for i in spec["inputs"]] == ["INV-QTY", "INV-UNIT-PRICE", "INV-CUST-TIER"]


def test_validate_spec_catches_bad_shapes():
    assert es.validate_spec([]) != []
    bad = {"module_id": "m", "summary": "s", "inputs": [{"name": "a"}], "outputs": [],
           "business_rules": "x", "edge_cases": [], "quirks": []}
    errs = es.validate_spec(bad)
    assert any("inputs[0].type" in e for e in errs) and any("outputs" in e for e in errs)
    assert any("business_rules" in e for e in errs)


# ---------------------------------------------------------------- generate_inputs
def test_generate_inputs_dedupes_and_adds_baseline(monkeypatch):
    monkeypatch.setattr(_llm, "call_llm", fake_call_llm)
    src = (SAMPLES / "interest.cbl").read_text()
    inputs = _generate_inputs({"module_id": "interest"}, src)
    assert len(inputs) == len(set(inputs)) and 20 <= len(inputs) <= 32
    assert "0" * 15 in inputs and "9" * 15 in inputs
    assert all("\n" not in i for i in inputs)


def test_generate_inputs_asks_for_more_when_short(monkeypatch, invoice_src):
    calls = []

    def llm(model, system, user, schema=None):
        calls.append(user)
        n = 5 if len(calls) == 1 else 20
        return {"cases": [{"input": f"{len(calls)}{i:011d}"[:12], "covers": "x"} for i in range(n)]}

    monkeypatch.setattr(_llm, "call_llm", llm)
    inputs = _generate_inputs({"module_id": "invoice"}, invoice_src)
    assert len(calls) == 2 and "MORE distinct cases" in calls[1]
    assert len(inputs) >= 20
    assert gi.LAST_RUN["cases"] and calls  # LAST_RUN populated for the eval


def test_generate_inputs_drops_multiline_and_accepts_plain_strings(monkeypatch, invoice_src):
    good = [f"{i:04d}0001000G" for i in range(1, 25)]
    monkeypatch.setattr(_llm, "call_llm", lambda *a, **k: {"cases": good + ["bad\nline"]})
    inputs = _generate_inputs({}, invoice_src)
    assert inputs == good


# ---------------------------------------------------------------- json helper
@pytest.mark.parametrize("text", [
    '{"a": 1}', '<think>hmm {"no": 1</think>{"a": 1}', 'Sure!\n```json\n{"a": 1}\n```', 'prefix {"a": 1} suffix'])
def test_extract_json(text):
    assert extract_json(text) == {"a": 1}


def test_extract_json_raises():
    with pytest.raises(ValueError):
        extract_json("no json here")


def _boom(*a, **k):
    raise TimeoutError("read timed out")


def test_extract_spec_survives_llm_exception(monkeypatch, invoice_src):
    monkeypatch.setattr(_llm, "call_llm", _boom)
    spec = _extract_spec(invoice_src)
    assert es.validate_spec(spec) == []
    assert any("WS-DISC-AMT" in q for q in spec["quirks"])


def test_generate_inputs_survives_llm_exception(monkeypatch, invoice_src):
    monkeypatch.setattr(_llm, "call_llm", _boom)
    inputs = _generate_inputs({}, invoice_src)
    assert inputs and all(len(i) == 12 for i in inputs)  # baseline cases still produced
