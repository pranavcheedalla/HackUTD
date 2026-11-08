"""Final-check hardening: rewrites must compute (never look up) answers, bad agent output
degrades gracefully, and the CLI fails with a message instead of a traceback."""
from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import testing  # noqa: E402
import importlib  # noqa: E402
rewrite_mod = importlib.import_module("agents.rewrite")
from pipeline import graph, status  # noqa: E402

CHEATS = {
    "open": "def main(s):\n    return open('golden/interest.jsonl').read()\n",
    "pathlib": "import pathlib\ndef main(s):\n    return pathlib.Path('golden/x').read_text()\n",
    "os": "import os\ndef main(s):\n    return os.popen('cat golden/x').read()\n",
    "subprocess": "import subprocess\ndef main(s):\n    return subprocess.check_output(['cat', 'x'])\n",
    "dynamic import": "def main(s):\n    return __import__('pathlib').Path('g').read_text()\n",
    "variable import": "m = 'os'\ndef main(s):\n    return __import__(m).getcwd()\n",
    "sys.modules": "import sys\ndef main(s):\n    return str(sys.modules)\n",
    "builtins": "def main(s):\n    return __builtins__['open']('g').read()\n",
    "subclasses": "def main(s):\n    return str(().__class__.__base__.__subclasses__())\n",
    "frames": "import sys\ndef main(s):\n    return str(sys._getframe().f_back.f_globals)\n",
    "eval": "def main(s):\n    return eval(s)\n",
    "relative import": "from . import x\ndef main(s):\n    return s\n",
}


@pytest.mark.parametrize("name", sorted(CHEATS))
def test_rewrite_that_reaches_outside_itself_is_rejected(name):
    assert testing.rewrite_violations(CHEATS[name]), name


def test_every_reference_and_recorded_rewrite_is_allowed():
    files = (glob.glob(str(ROOT / "tests/fixtures/*_reference.py"))
             + glob.glob(str(ROOT / "tests/fixtures/codebase/modern/*.py"))
             + glob.glob(str(ROOT / "docs/evidence/*/modern/*.py")))
    assert len(files) >= 9
    for f in files:
        assert testing.rewrite_violations(Path(f).read_text(), ["discount"]) == [], f


def test_script_block_and_inline_safe_import_are_allowed():
    src = ("def main(s):\n    return __import__('re').sub('a', 'b', s)\n"
           "if __name__ == '__main__':\n    import sys\n    print(main(sys.stdin.readline()))\n")
    assert testing.rewrite_violations(src) == []


def test_dependency_import_needs_the_dependency_to_be_declared():
    src = "import discount\ndef main(s):\n    return s\n"
    assert testing.rewrite_violations(src)
    assert testing.rewrite_violations(src, ["discount"]) == []


def test_rewrite_agent_tells_the_model_why_a_cheat_is_invalid():
    err = rewrite_mod.validate(CHEATS["open"])
    assert err and "open()" in err and "input_line" in err


@pytest.fixture
def quiet(monkeypatch, tmp_path):
    monkeypatch.setattr(status, "STATE_PATH", tmp_path / "state.json")
    status.start_run(["interest"])
    return tmp_path


def test_verify_rejects_cheating_rewrite_without_running_it(quiet, monkeypatch):
    monkeypatch.setattr(graph.testing, "run_equivalence",
                        lambda mid: pytest.fail("a cheating rewrite must never be executed"))
    out = graph.verify({"id": "interest", "python_src": CHEATS["open"], "dep_modules": []})
    assert out["status"] == "failed" and out["error"].startswith("rejected:")


def test_verify_refuses_to_accept_on_too_few_cases(quiet, monkeypatch):
    monkeypatch.setattr(graph.testing, "run_equivalence",
                        lambda mid: {"passed": 1, "total": 1, "failures": []})
    out = graph.verify({"id": "interest", "python_src": "def main(s):\n    return s\n", "dep_modules": []})
    assert out["status"] == "failed" and "too few" in out["error"]


def test_verify_passes_through_a_normal_result(quiet, monkeypatch):
    monkeypatch.setattr(graph.testing, "run_equivalence",
                        lambda mid: {"passed": 20, "total": 20, "failures": []})
    out = graph.verify({"id": "interest", "python_src": "def main(s):\n    return s\n", "dep_modules": []})
    assert out["status"] == "verifying" and out["tests_passed"] == 20


def test_clean_inputs_drops_bad_lines_and_duplicates_in_order():
    raw = ["a|1", "a|1", "", "x\ny", "r\r", 7, None, "b|2", ""]
    assert graph.clean_inputs(raw) == (["a|1", "", "b|2"], 6)


def test_clean_inputs_rejects_a_non_list():
    with pytest.raises(TypeError):
        graph.clean_inputs("a|1")


def _run_cli(*args):
    env = dict(os.environ, LLM_MODE="fake")
    return subprocess.run([sys.executable, str(ROOT / "run.py"), *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60)


def test_cli_missing_folder_is_a_message_not_a_traceback(tmp_path):
    p = _run_cli(str(tmp_path / "nope"))
    assert p.returncode == 1 and "not found" in p.stderr and "Traceback" not in p.stderr


def test_cli_unknown_only_lists_the_real_modules():
    p = _run_cli(str(ROOT / "legacy"), "--only", "nope")
    assert p.returncode == 1 and "interest" in p.stderr and "Traceback" not in p.stderr


test_writer = importlib.import_module("agents.test_writer")
_nemotron = importlib.import_module("agents._nemotron")


def test_disputed_unit_tests_are_quarantined_not_deleted(monkeypatch):
    bad = ("```python\nimport pytest\nfrom modern.m9 import main\n\n"
           "def test_ok():\n    assert main('') == 'Z'\n\n"
           "@pytest.mark.parametrize('x', ['a', 'b'])\ndef test_wrong_guess(x):\n    assert main(x) == 'nope'\n\n"
           "@pytest.fixture\ndef broken():\n    raise ValueError('setup')\n\n"
           "def test_setup_error(broken):\n    assert True\n```")
    monkeypatch.setattr(_nemotron, "call_llm", lambda *a: bad)
    with pytest.raises(test_writer.UnitTestsNeedReview) as info:
        test_writer.write_unit_tests({"module_id": "m9"}, "def main(s):\n    return 'Z'\n")
    err = info.value
    assert err.quarantined == ["test_setup_error", "test_wrong_guess"]
    assert "def test_ok" in err.code and "def test_wrong_guess" in err.code   # nothing deleted
    assert err.code.count("@pytest.mark.skip(reason=") == 2
    assert "quarantined for review" in err.code.splitlines()[0]


def test_accept_keeps_quarantined_unit_tests_and_flags_review(quiet, monkeypatch):
    monkeypatch.setattr(graph, "UNIT_DIR", quiet / "unit")

    def writer(spec, src):
        raise test_writer.UnitTestsNeedReview("x", code="# kept\n", quarantined=["test_a"])
    monkeypatch.setattr(graph.agents, "write_unit_tests", writer)
    out = graph.accept({"id": "interest", "spec": {}, "python_src": "def main(s): return s\n"})
    assert out["status"] == "done" and out["unit_tests_status"] == "needs_review"
    assert out["unit_tests_quarantined"] == ["test_a"]
    assert (quiet / "unit" / "test_interest_unit.py").read_text() == "# kept\n"
