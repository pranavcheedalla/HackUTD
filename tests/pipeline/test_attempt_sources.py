"""Every rewrite's source is kept in state["attempt_sources"], so a replay can show what the
agent changed between attempts even though modern/<id>.py is overwritten on each retry."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline import graph, status  # noqa: E402


@pytest.fixture
def quiet(monkeypatch, tmp_path):
    monkeypatch.setattr(status, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(graph, "MODERN_DIR", tmp_path / "modern")
    monkeypatch.setattr(graph.testing, "golden_to_pytest", lambda *a, **k: None)
    status.start_run(["invoice"])
    return tmp_path


def _state(**extra):
    return {"id": "invoice", "spec": {}, "cobol_src": "COBOL", "dep_modules": [], **extra}


def _rewrite_returns(monkeypatch, *sources):
    queue = list(sources)
    monkeypatch.setattr(graph.agents, "rewrite", lambda *a, **k: queue.pop(0))


def test_each_attempt_keeps_its_source(quiet, monkeypatch):
    first, second = "def main(s):\n    return s\n", "def main(s):\n    return s.strip()\n"
    _rewrite_returns(monkeypatch, first, second)
    out = graph.rewrite(_state())
    out = graph.rewrite({**out, "last_failures": [{"input": "x", "expected": "a", "actual": "b"}]})
    assert [s["attempt"] for s in out["attempt_sources"]] == [1, 2]
    assert [s["python"] for s in out["attempt_sources"]] == [first, second]


def test_attempt_sources_is_a_declared_graph_key():
    # LangGraph silently drops undeclared keys between nodes
    assert "attempt_sources" in graph.GraphState.__annotations__


def test_long_source_is_cut_to_20000_chars(quiet, monkeypatch):
    _rewrite_returns(monkeypatch, "x" * 30000)
    out = graph.rewrite(_state())
    (rec,) = out["attempt_sources"]
    assert rec["attempt"] == 1 and len(rec["python"]) == 20000
