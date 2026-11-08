"""Every verify is kept in state["history"], so a replay can show the real mismatch and
the explanation even after the module later passes."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline import graph, status  # noqa: E402

FAIL = {"input": "1|12.35|0.01", "expected": "TOTAL=00012.34", "actual": "TOTAL=00012.35"}


@pytest.fixture
def quiet(monkeypatch, tmp_path):
    monkeypatch.setattr(status, "STATE_PATH", tmp_path / "state.json")
    status.start_run(["invoice"])
    return tmp_path


def _state(**extra):
    return {"id": "invoice", "spec": {}, "cobol_src": "COBOL", "python_src": "def main(s):\n    return s\n",
            "dep_modules": [], "attempts": 1, **extra}


def _equivalence(monkeypatch, passed, failures):
    monkeypatch.setattr(graph.testing, "run_equivalence",
                        lambda mid: {"passed": passed, "total": 30, "failures": failures})


def test_failed_attempt_keeps_cases_and_one_explanation(quiet, monkeypatch):
    _equivalence(monkeypatch, 26, [FAIL] * 4)
    calls = []
    monkeypatch.setattr(graph.agents, "explain_divergence",
                        lambda *a: calls.append(a[3]) or {"verdict": "new_code_bug", "reason": "rounds instead of truncating"})
    out = graph.verify(_state())
    (rec,) = out["history"]
    assert rec["attempt"] == 1 and rec["passed"] == 26 and rec["total"] == 30
    assert rec["failures"][0] == FAIL and len(rec["failures"]) == 4
    assert rec["explanation"] == {"verdict": "new_code_bug", "reason": "rounds instead of truncating",
                                  "input": FAIL["input"]}
    assert calls == [FAIL]   # one model call per retried attempt


def test_history_accumulates_and_a_pass_needs_no_explanation(quiet, monkeypatch):
    first = {"attempt": 1, "passed": 26, "total": 30, "failures": [FAIL], "explanation": None}
    _equivalence(monkeypatch, 30, [])
    monkeypatch.setattr(graph.agents, "explain_divergence", lambda *a: pytest.fail("no explanation needed"))
    out = graph.verify(_state(attempts=2, history=[first]))
    assert [r["attempt"] for r in out["history"]] == [1, 2]
    assert out["history"][1]["failures"] == [] and out["history"][1]["explanation"] is None


def test_last_attempt_leaves_explaining_to_the_explain_node(quiet, monkeypatch):
    _equivalence(monkeypatch, 26, [FAIL])
    monkeypatch.setattr(graph.agents, "explain_divergence", lambda *a: pytest.fail("explain node does this"))
    out = graph.verify(_state(attempts=graph.MAX_ATTEMPTS))
    assert out["history"][0]["explanation"] is None and out["status"] == "verifying"


def test_explainer_outage_never_fails_the_module(quiet, monkeypatch):
    _equivalence(monkeypatch, 26, [FAIL])

    def down(*a):
        raise RuntimeError("503")
    monkeypatch.setattr(graph.agents, "explain_divergence", down)
    out = graph.verify(_state())
    assert out["status"] == "verifying"
    assert out["history"][0]["explanation"]["reason"] == "explainer unavailable: RuntimeError"


def test_recorded_failures_are_capped(quiet, monkeypatch):
    _equivalence(monkeypatch, 10, [dict(FAIL, input=str(i)) for i in range(20)])
    monkeypatch.setattr(graph.agents, "explain_divergence", lambda *a: {"verdict": "new_code_bug", "reason": "r"})
    out = graph.verify(_state())
    assert len(out["history"][0]["failures"]) == graph.MAX_RECORDED_FAILURES


def test_history_is_a_declared_graph_key():
    # LangGraph silently drops undeclared keys between nodes
    assert "history" in graph.GraphState.__annotations__


def test_retry_gets_the_explanation_with_the_failing_case(quiet, monkeypatch):
    _equivalence(monkeypatch, 26, [FAIL])
    monkeypatch.setattr(graph.agents, "explain_divergence",
                        lambda *a: {"verdict": "new_code_bug", "reason": "COBOL truncates; the rewrite rounded."})
    out = graph.verify(_state())
    assert out["last_failures"][0]["why"] == "COBOL truncates; the rewrite rounded."
    assert "why" not in out["history"][0]["failures"][0]  # the recorded case stays as it was
    import importlib
    text = importlib.import_module("agents.rewrite").format_failures(out["last_failures"])
    assert "why:      COBOL truncates; the rewrite rounded." in text
