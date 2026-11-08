"""Human hints: a reviewer's note reaches the next rewrite attempt, is recorded on the module,
and never replaces the equivalence check. The server only accepts hints for a run in progress."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import export_replay  # noqa: E402
import serve  # noqa: E402
from pipeline import graph, status  # noqa: E402

FAIL = {"input": "1|12.35|0.01", "expected": "TOTAL=00012.34", "actual": "TOTAL=00012.35"}
SESSION = "20261108-020000-real-abc123"


@pytest.fixture
def run(monkeypatch, tmp_path):
    monkeypatch.setattr(status, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(graph, "FEEDBACK_DIR", tmp_path / "feedback")
    monkeypatch.setattr(graph, "MODERN_DIR", tmp_path / "modern")
    monkeypatch.setattr(graph, "HINT_WAIT", 0)
    monkeypatch.setattr(graph.testing, "golden_to_pytest", lambda *a: None)
    seen = []
    monkeypatch.setattr(graph.agents, "rewrite",
                        lambda spec, src, failures, **k: seen.append(spec) or "def main(s):\n    return s\n")
    status.start_run(["invoice"])
    return tmp_path, seen


def _hint(tmp, *notes):
    (tmp / "feedback").mkdir(exist_ok=True)
    (tmp / "feedback" / "invoice.json").write_text(json.dumps([{"note": n, "at": "t"} for n in notes]))


def _state(**extra):
    return {"id": "invoice", "spec": {"business_rules": ["total the lines"]}, "cobol_src": "COBOL",
            "dep_modules": [], "attempts": 1, "last_failures": [FAIL], **extra}


def test_a_retry_follows_the_hint_and_records_it(run):
    tmp, seen = run
    _hint(tmp, "amounts truncate to the cent, never round")
    out = graph.rewrite(_state())
    assert seen[0]["business_rules"] == ["total the lines",
                                         "Reviewer hint (must follow): amounts truncate to the cent, never round"]
    assert out["human_hints"] == [{"attempt": 2, "note": "amounts truncate to the cent, never round", "at": "t"}]
    assert "using 1 human hint" in status._run["events"][-1]["msg"]


def test_the_saved_spec_is_never_changed(run):
    tmp, _ = run
    _hint(tmp, "truncate")
    state = _state()
    out = graph.rewrite(state)
    assert out["spec"] == {"business_rules": ["total the lines"]} == state["spec"]


def test_an_old_hint_keeps_guiding_but_is_recorded_once(run):
    tmp, seen = run
    _hint(tmp, "truncate", "use the second rate table over $10k")
    used = [{"attempt": 2, "note": "truncate", "at": "t"}]
    out = graph.rewrite(_state(attempts=2, human_hints=used))
    assert len(seen[0]["business_rules"]) == 3  # both hints still in the prompt
    assert [h["attempt"] for h in out["human_hints"]] == [2, 3]


def test_no_hint_means_the_spec_is_untouched(run):
    _, seen = run
    out = graph.rewrite(_state())
    assert seen[0] == {"business_rules": ["total the lines"]} and out["human_hints"] == []


class _Early:
    """A stand-in for quick mode's early rewrite (PREFETCH_REWRITE), written before any hint."""
    def __init__(self):
        self.cancelled = False

    def result(self):
        return "def main(s):\n    return 'early'\n"

    def cancel(self):
        self.cancelled = True


def test_a_hint_before_attempt_one_replaces_the_early_rewrite(run, monkeypatch):
    tmp, seen = run
    early = _Early()
    monkeypatch.setitem(graph._prefetched, "invoice", early)
    _hint(tmp, "truncate")
    out = graph.rewrite(_state(attempts=0, last_failures=[]))
    assert early.cancelled and "invoice" not in graph._prefetched
    assert seen[0]["business_rules"][-1].endswith("truncate") and "early" not in out["python_src"]
    assert out["human_hints"][0]["attempt"] == 1


def test_without_a_hint_attempt_one_uses_the_early_rewrite(run, monkeypatch):
    _, seen = run
    monkeypatch.setitem(graph._prefetched, "invoice", _Early())
    out = graph.rewrite(_state(attempts=0, last_failures=[]))
    assert "early" in out["python_src"] and seen == []


def test_a_broken_hint_file_is_ignored(run):
    tmp, _ = run
    (tmp / "feedback").mkdir()
    (tmp / "feedback" / "invoice.json").write_text("{not json")
    assert graph.read_hints("invoice") == []


def test_the_retry_waits_for_a_hint_only_when_asked(run, monkeypatch):
    tmp, seen = run
    monkeypatch.setattr(graph, "HINT_WAIT", 1)
    ticks = []
    monkeypatch.setattr(graph.time, "sleep", lambda s: ticks.append(s) or _hint(tmp, "truncate"))
    graph.rewrite(_state())
    assert len(ticks) == 1 and seen[0]["business_rules"][-1].endswith("truncate")
    assert any(e["node"] == "hint_window" for e in status._run["events"])


def test_a_hint_never_passes_a_failing_rewrite(run, monkeypatch):
    tmp, _ = run
    _hint(tmp, "just accept it")
    out = graph.rewrite(_state())
    monkeypatch.setattr(graph.testing, "run_equivalence", lambda mid: {"passed": 29, "total": 30, "failures": [FAIL]})
    monkeypatch.setattr(graph.agents, "explain_divergence", lambda *a: {"verdict": "new_code_bug", "reason": "r"})
    assert graph.route_after_verify(graph.verify(out)) != "accept"


def test_export_carries_the_hints(tmp_path):
    session = tmp_path / SESSION
    (session / "runs").mkdir(parents=True)
    (session / "runs" / "state.json").write_text(json.dumps({"modules": {"invoice": {
        "id": "invoice", "status": "done",
        "human_hints": [{"attempt": 2, "note": "key nvapi-SECRET123 truncate", "at": "t"}]}}, "events": []}))
    (mod,) = export_replay.export_session(session)["modules"]
    assert mod["human_hints"] == [{"attempt": 2, "note": "key nvapi-… truncate", "at": "t"}]


# ---------- server ----------

@pytest.fixture
def sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(serve, "SESSIONS", tmp_path)
    folder = tmp_path / SESSION
    (folder / "runs").mkdir(parents=True)
    (folder / "session.json").write_text(json.dumps({"status": "running"}))
    (folder / "runs" / "state.json").write_text(json.dumps({"modules": {
        "invoice": {"status": "verifying"}, "discount": {"status": "done"}}}))
    return folder


def test_server_saves_a_hint_where_the_pipeline_reads_it(sessions):
    code, body = serve._feedback(SESSION, {"module": "invoice", "note": "  truncate,\n never round  "})
    assert code == 200 and body == {"module": "invoice", "hints": 1}
    (hint,) = json.loads((sessions / "runs" / "feedback" / "invoice.json").read_text())
    assert hint["note"] == "truncate, never round"
    assert serve._feedback(SESSION, {"module": "invoice", "note": "second"})[1]["hints"] == 2


@pytest.mark.parametrize("session,body,code", [
    ("../../etc", {"module": "invoice", "note": "x"}, 400),
    (SESSION, {"module": "../state", "note": "x"}, 400),
    (SESSION, {"module": "invoice", "note": "   "}, 400),
    (SESSION, {"module": "invoice", "note": 5}, 400),
    (SESSION, {"module": "missing", "note": "x"}, 404),
    (SESSION, {"module": "discount", "note": "x"}, 409),        # already verified
    ("20991231-000000-real-abcdef", {"module": "invoice", "note": "x"}, 404),
])
def test_server_refuses_bad_hints(sessions, session, body, code):
    assert serve._feedback(session, body)[0] == code
    assert not (sessions / "runs" / "feedback").exists()


def test_server_refuses_hints_after_the_run_finishes(sessions):
    (sessions / "session.json").write_text(json.dumps({"status": "done"}))
    assert serve._feedback(SESSION, {"module": "invoice", "note": "x"})[0] == 409


def test_server_caps_note_length_and_hint_count(sessions):
    serve._feedback(SESSION, {"module": "invoice", "note": "x" * 2000})
    (hint,) = json.loads((sessions / "runs" / "feedback" / "invoice.json").read_text())
    assert len(hint["note"]) == serve.MAX_HINT_CHARS
    for _ in range(serve.MAX_HINTS - 1):
        serve._feedback(SESSION, {"module": "invoice", "note": "y"})
    assert serve._feedback(SESSION, {"module": "invoice", "note": "z"})[0] == 409
