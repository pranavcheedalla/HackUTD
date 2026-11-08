"""Human feedback: when the agent runs out of attempts, the module waits in needs_review for a
person; their note reaches the next rewrite attempts, is recorded on the module, and never
replaces the equivalence check. The server only accepts feedback for a module that is asking."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
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
    monkeypatch.setattr(graph, "REVIEW_WAIT", 0)
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


def _stuck(**extra):
    hist = [{"attempt": 3, "passed": 24, "total": 26, "failures": [FAIL], "explanation": None}]
    return _state(**{"attempts": 3, "history": hist, "python_src": "def main(s):\n    return s\n", **extra})


def test_without_a_review_window_a_stuck_module_fails_as_before(run, monkeypatch):
    monkeypatch.setattr(graph.time, "sleep", lambda s: pytest.fail("must not wait"))
    state = _stuck()
    assert graph.route_after_verify(state) == "review"
    out = graph.needs_review(state)
    assert out == state and graph.route_after_review(out) == "explain"


def test_feedback_in_the_review_window_buys_more_attempts(run, monkeypatch):
    tmp, _ = run
    monkeypatch.setattr(graph, "REVIEW_WAIT", 30)
    monkeypatch.setattr(graph.agents, "explain_divergence", lambda *a: {"verdict": "legacy_quirk", "reason": "cuts off cents"})
    seen = []
    monkeypatch.setattr(graph.time, "sleep", lambda s: seen.append(status._run["modules"]["invoice"]["status"]) or _hint(tmp, "truncate"))
    out = graph.needs_review(_stuck())
    assert seen == ["needs_review"]  # the dashboard and galaxy saw it asking
    assert out["status"] == "verifying" and out["reviews"] == 1 and out["attempt_limit"] == 3 + graph.EXTRA_ATTEMPTS
    assert out["history"][-1]["explanation"]["reason"] == "cuts off cents"  # the person sees why
    assert out["last_failures"][0]["why"] == "cuts off cents"
    assert graph.route_after_review(out) == "retry"
    assert graph.route_after_verify({**out, "attempts": 4}) == "retry"
    assert graph.route_after_verify({**out, "attempts": 5}) == "review"


def test_no_answer_in_the_review_window_goes_on_to_explain(run, monkeypatch):
    monkeypatch.setattr(graph, "REVIEW_WAIT", 0.01)
    monkeypatch.setattr(graph.agents, "explain_divergence", lambda *a: {"verdict": "new_code_bug", "reason": "r"})
    nap = time.sleep
    monkeypatch.setattr(graph.time, "sleep", lambda s: nap(0.01))
    out = graph.needs_review(_stuck())
    assert out["status"] == "verifying" and "attempt_limit" not in out
    assert graph.route_after_review(out) == "explain"
    assert status._run["events"][-1]["msg"] == "no feedback; explaining the differences"


def test_a_module_asks_for_help_at_most_twice(run, monkeypatch):
    monkeypatch.setattr(graph, "REVIEW_WAIT", 30)
    monkeypatch.setattr(graph.time, "sleep", lambda s: pytest.fail("must not wait"))
    state = _stuck(reviews=graph.MAX_REVIEWS, attempt_limit=7, attempts=7)
    assert graph.route_after_review(graph.needs_review(state)) == "explain"


def test_offline_run_waits_for_a_person_and_their_feedback_fixes_it(tmp_path):
    project = tmp_path / "project"
    shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(
        ".git", ".env", "__pycache__", ".pytest_cache", ".cache", ".venv*", "bin", "runs", "modern",
        "specs", "equivalence", "unit", "validation", "samples"))
    env = dict(os.environ, LLM_MODE="fake", DEMO_SCENARIO="review", REVIEW_WAIT="30",
               LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false")
    env.pop("NVIDIA_API_KEY", None)
    proc = subprocess.Popen([sys.executable, str(project / "run.py"), "--only", "invoice"], cwd=project,
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    state_path = project / "runs" / "state.json"
    try:
        for _ in range(200):
            try:
                if json.loads(state_path.read_text())["modules"]["invoice"]["status"] == "needs_review":
                    break
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(0.1)
        else:
            pytest.fail("invoice never asked for help")
        (project / "runs" / "feedback").mkdir(parents=True, exist_ok=True)
        (project / "runs" / "feedback" / "invoice.json").write_text(json.dumps(
            [{"note": "fractions of a cent are cut off, never rounded", "at": "t"}]))
        out = proc.communicate(timeout=60)[0]
    finally:
        proc.kill()
    assert proc.returncode == 0, out
    inv = json.loads(state_path.read_text())["modules"]["invoice"]
    assert inv["status"] == "done" and inv["attempts"] == 4 and inv["reviews"] == 1
    assert inv["human_hints"][0]["attempt"] == 4
    assert [h["passed"] < h["total"] for h in inv["history"]] == [True, True, True, False]


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
        "invoice": {"status": "needs_review"}, "discount": {"status": "done"},
        "interest": {"status": "verifying"}}}))
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
    (SESSION, {"module": "interest", "note": "x"}, 409),        # still trying on its own
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
