"""One program live: a real ~25 s run for each judge, with the same verification."""
from concurrent.futures import Future
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import serve  # noqa: E402
from pipeline import graph  # noqa: E402


def test_server_only_accepts_a_real_program_of_the_codebase():
    assert serve._start("samples/bank", only="nope")[0] == 400
    assert serve._start("samples/bank", only="../etc")[0] == 400
    assert serve._start("samples/nowhere", only="loanpay")[0] == 400


def test_quick_run_skips_only_the_slow_extras():
    assert serve.QUICK_ENV == {"SKIP_UNIT_TESTS": "1", "PREFETCH_REWRITE": "1",
                               "LLM_SPEC_REVIEW": "0", "SPEC_MODEL": "super"}


def test_accept_skips_unit_tests_in_a_quick_run(monkeypatch):
    monkeypatch.setenv("SKIP_UNIT_TESTS", "1")
    monkeypatch.setattr(graph.status, "update", lambda *a, **k: None)
    out = graph.accept({"id": "loanpay", "status": "verifying"})
    assert out["status"] == "done" and out["unit_tests_status"] == "skipped"


def test_early_rewrite_is_used_once_and_falls_back_on_error(monkeypatch):
    calls = []
    monkeypatch.setattr(graph.agents, "rewrite", lambda spec, src, failures: calls.append(1) or "direct")
    state = {"id": "m", "spec": {}, "cobol_src": ""}
    done = Future(); done.set_result("early")
    graph._prefetched["m"] = done
    assert graph._first_rewrite(state) == "early" and not calls
    broken = Future(); broken.set_exception(RuntimeError("timeout"))
    graph._prefetched["m"] = broken
    assert graph._first_rewrite(state) == "direct" and calls == [1]
    assert graph._first_rewrite(state) == "direct"  # nothing prefetched: the normal call


def test_no_early_rewrite_unless_asked_or_with_dependencies(monkeypatch):
    graph._prefetched.clear()
    monkeypatch.delenv("PREFETCH_REWRITE", raising=False)
    graph._prefetch_rewrite({"id": "a", "cobol_src": ""}, {})
    monkeypatch.setenv("PREFETCH_REWRITE", "1")
    graph._prefetch_rewrite({"id": "b", "cobol_src": "", "dep_modules": [{"module_id": "x"}]}, {})
    assert graph._prefetched == {}


def test_one_program_live_never_waits_for_a_person(monkeypatch):
    seen = {}

    class Proc:
        def poll(self): return 0
        def terminate(self): pass

    def popen(cmd, cwd, stdout, stderr, env):
        seen[cmd[cmd.index("--legacy-dir") + 1]] = env
        return Proc()

    monkeypatch.setattr(serve, "_api_key", lambda: True)
    monkeypatch.setattr(serve.subprocess, "Popen", popen)
    monkeypatch.setattr(serve.time, "sleep", lambda s: None)
    serve._start("samples/bank", only="loanpay", quick=True)
    serve._start("samples/review", only="settle", quick=True)
    assert seen["samples/bank"]["REVIEW_WAIT"] == "0"
    assert seen["samples/review"]["REVIEW_WAIT"] != "0" and seen["samples/review"]["MAX_ATTEMPTS"] == "1"


def test_the_demo_recordings_go_live_with_loanpay_never_settle():
    """One program live must run the program tested live 10 times, never the one built to need a person."""
    import json
    for name in ("retail", "bank"):
        rep = json.loads((ROOT / "web" / "replays" / f"{name}.json").read_text())
        assert rep["quick_live"] == "loanpay"
        m = next(m for m in rep["modules"] if m["id"] == "loanpay")
        assert m["kind"] != "subprogram" and not m.get("depends_on") and m["status"] == "done"
        assert len(m["history"]) == 1 and not m.get("human_hints")
    galaxy = (ROOT / "web" / "galaxy.js").read_text()
    assert "R.quick_live" in galaxy and "!(m.human_hints || []).length" in galaxy
