"""Offline tests for P4 agents: no API key, no cobc. Run: pytest dev/p4 -q"""
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import importlib  # noqa: E402

from agents import _llm, explainer, test_writer  # noqa: E402

rewrite_mod = importlib.import_module("agents.rewrite")  # attribute is shadowed by the function
from agents.cobol_helpers import display_num, edit_picture, pic_from_text, pic_store, split_fixed  # noqa: E402


# ---------------------------------------------------------------- COBOL helpers
@pytest.mark.parametrize("value,pic,expected", [
    (0, "Z,ZZZ,ZZ9.99", "        0.00"),
    (Decimal("287.77"), "Z,ZZZ,ZZ9.99", "      287.77"),
    (Decimal("1522.33"), "ZZ,ZZZ,ZZ9.99", "     1,522.33"),
    (Decimal("1234567.891"), "Z,ZZZ,ZZ9.99", "1,234,567.89"),   # truncates
    (Decimal("-12.5"), "-ZZ9.99", "- 12.50"),
    (Decimal("12.5"), "-ZZ9.99", "  12.50"),
    (Decimal("-12.5"), "ZZ9.99CR", " 12.50CR"),
    (Decimal("12.5"), "ZZ9.99CR", " 12.50  "),
    (Decimal("42"), "9(5)", "00042"),
    (0, "ZZZ", "   "),
    (Decimal("5"), "$ZZ9.99", "$  5.00"),
])
def test_edit_picture(value, pic, expected):
    assert edit_picture(value, pic) == expected


def test_pic_store_truncates_and_overflows():
    assert pic_store(Decimal("287.775936"), 7, 2) == Decimal("287.77")
    assert pic_store(Decimal("287.775936"), 7, 2, rounded=True) == Decimal("287.78")
    assert pic_store(Decimal("12345678.99"), 7, 2) == Decimal("2345678.99")
    assert pic_store(Decimal("-5"), 3) == Decimal("5")
    assert pic_store(Decimal("-5"), 3, signed=True) == Decimal("-5")


def test_input_parsing_and_display():
    assert split_fixed("12345", [2, 2, 3]) == ["12", "34", "5  "]
    assert pic_from_text("0012345", 5, 2) == Decimal("123.45")
    assert pic_from_text("  ", 2) == 0
    assert display_num(Decimal("1.5"), 3, 2) == "001.50"
    assert display_num(Decimal("-7"), 3, 0, signed=True) == "-007"


# ---------------------------------------------------------------- rewrite agent (fake LLM)
def test_rewrite_inlines_helpers_and_retries_on_syntax_error(monkeypatch):
    replies = iter([
        "```python\ndef main(input_line):\n    return 'x' +\n```",  # broken
        "<think>hmm</think>```python\nfrom decimal import Decimal\n"
        "def main(input_line: str) -> str:\n    return edit_picture(Decimal(1), 'Z9.99')\n```",
    ])
    calls = []
    monkeypatch.setattr(_llm, "call_llm", lambda *a: (calls.append(a), next(replies))[1])
    src = rewrite_mod.rewrite({"module_id": "m1"}, "COBOL", None)
    assert len(calls) == 2 and "SyntaxError" in calls[1][2]  # self-check fed the error back
    ns = {}
    exec(src, ns)
    assert ns["main"]("") == " 1.00"


def test_rewrite_fix_prompt_contains_previous_code_and_failures(monkeypatch):
    good = "```python\ndef main(input_line):\n    return 'A'\n```"
    seen = []
    monkeypatch.setattr(_llm, "call_llm", lambda m, s, u, j: (seen.append(u), good)[1])
    rewrite_mod.rewrite({"module_id": "m2"}, "COBOL", None)
    rewrite_mod.rewrite({"module_id": "m2"}, "COBOL", [{"input": "1", "expected": "B", "actual": "A"}])
    assert "return 'A'" in seen[1] and "'B'" in seen[1]


def test_validate_rejects_missing_main_and_print():
    assert rewrite_mod.validate("x = 1") is not None
    assert rewrite_mod.validate("def main(s):\n    print(s)") is not None
    assert rewrite_mod.validate("def main(s):\n    return s\nif __name__ == '__main__':\n    print(main(input()))") is None


# ---------------------------------------------------------------- explainer
def test_explainer_heuristic_truncation():
    a = explainer.analyze_diff("INTEREST=      287.77", "INTEREST=      287.78")
    assert a["verdict"] == "legacy_quirk" and "rounding" in a["reason"]


def test_explainer_heuristic_overflow_and_format():
    assert explainer.analyze_diff("TOTAL=2,345,678.99", "TOTAL=12,345,678.99")["verdict"] == "legacy_quirk"
    assert explainer.analyze_diff("TOTAL=  5.00", "TOTAL=5.00")["verdict"] == "new_code_bug"
    assert explainer.analyze_diff("TOTAL=15.00", "TOTAL=30.00")["verdict"] == "new_code_bug"


def test_explainer_uses_llm_and_trims_to_one_sentence(monkeypatch):
    monkeypatch.setattr(_llm, "call_llm", lambda *a: {"verdict": "legacy_quirk",
                                                      "reason": "Old system truncates cents. Second sentence."})
    out = explainer.explain_divergence({}, "C", "P", {"input": "i", "expected": "1.00", "actual": "1.01"})
    assert out == {"verdict": "legacy_quirk", "reason": "Old system truncates cents."}


def test_explainer_falls_back_when_llm_fails(monkeypatch):
    def boom(*a):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(_llm, "call_llm", boom)
    out = explainer.explain_divergence({}, "C", "P", {"input": "i", "expected": "287.77", "actual": "287.78"})
    assert out["verdict"] == "legacy_quirk"


# ---------------------------------------------------------------- test writer
def test_test_writer_retries_when_import_missing(monkeypatch):
    replies = iter([
        "```python\ndef test_a():\n    assert True\n```",
        "```python\nfrom modern.m3 import main\n\ndef test_a():\n    assert isinstance(main(''), str)\n```",
    ])
    monkeypatch.setattr(_llm, "call_llm", lambda *a: next(replies))
    src = test_writer.write_unit_tests({"module_id": "m3"}, "def main(s): return s")
    assert "from modern.m3 import main" in src


def test_rewrite_self_check_replays_failures_until_fixed(monkeypatch):
    replies = iter([
        "```python\ndef main(input_line):\n    return 'A'\n```",          # still wrong
        "```python\ndef main(input_line):\n    return 'B'\n```",          # fixed
    ])
    seen = []
    monkeypatch.setattr(_llm, "call_llm", lambda m, s, u, j: (seen.append(u), next(replies))[1])
    src = rewrite_mod.rewrite({"module_id": "m4"}, "COBOL", [{"input": "1", "expected": "B", "actual": "A"}])
    assert "'B'" in src and len(seen) == 2
    assert "still fail" in seen[1] and "'A'" in seen[1]


def test_rewrite_self_check_catches_crash(monkeypatch):
    replies = iter([
        "```python\ndef main(input_line):\n    return str(int(input_line))\n```",   # crashes on ''
        "```python\ndef main(input_line):\n    return str(int(input_line or 0))\n```",
    ])
    seen = []
    monkeypatch.setattr(_llm, "call_llm", lambda m, s, u, j: (seen.append(u), next(replies))[1])
    src = rewrite_mod.rewrite({"module_id": "m5"}, "COBOL", None)
    assert "or 0" in src and "ValueError" in seen[1]


def test_rewrite_returns_best_candidate_after_max_calls(monkeypatch):
    fails = [{"input": str(i), "expected": "X", "actual": "?"} for i in range(3)]
    replies = iter([
        "```python\ndef main(s):\n    return '?'\n```",                         # 3 wrong
        "```python\ndef main(s):\n    return 'X' if s != '2' else '?'\n```",   # 1 wrong (best)
        "```python\ndef main(s):\n    return 'X' if s == '9' else '?'\n```",   # 3 wrong
    ])
    monkeypatch.setattr(_llm, "call_llm", lambda *a: next(replies))
    src = rewrite_mod.rewrite({"module_id": "m6"}, "COBOL", fails)
    assert "s != '2'" in src


# ---------------------------------------------------------------- Nemotron client + trace
def test_trace_records_agent_and_nemotron_model(monkeypatch, tmp_path):
    trace = tmp_path / "trace.jsonl"
    monkeypatch.setattr(_llm, "TRACE_PATH", trace)
    monkeypatch.setattr(_llm, "_backend", lambda: (lambda *a: "ok", "fake"))
    with _llm.agent("rewrite", "mod1"):
        assert _llm.call_llm("super", "s", "u", None) == "ok"
    import json
    rec = json.loads(trace.read_text().splitlines()[-1])
    assert rec["agent"] == "rewrite" and rec["module_id"] == "mod1"
    assert rec["model_id"] == _llm.MODEL_IDS["super"] and "nemotron" in rec["model_id"]


def test_local_client_captures_reasoning_caches_and_parses_json(monkeypatch, tmp_path):
    monkeypatch.setattr(_llm, "_CACHE_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(_llm, "_invoke", lambda m, s, u: (calls.append(m), ('{"verdict": "legacy_quirk"}', "because cents", "nvidia/x"))[1])
    schema = {"type": "object"}
    assert _llm._local_call_llm("super", "s", "u", schema) == {"verdict": "legacy_quirk"}
    assert _llm.last_reasoning() == "because cents"
    assert _llm._local_call_llm("super", "s", "u", schema) == {"verdict": "legacy_quirk"}
    assert len(calls) == 1  # second call served from cache


def test_explainer_uses_nemotron_super(monkeypatch):
    models = []
    monkeypatch.setattr(_llm, "call_llm", lambda m, *a: (models.append(m), {"verdict": "new_code_bug", "reason": "x."})[1])
    explainer.explain_divergence({}, "C", "P", {"input": "i", "expected": "a", "actual": "b"})
    assert models == ["super"]


# ---------------------------------------------------------------- test writer runs its tests
def test_test_writer_repairs_then_drops_tests_that_still_fail(monkeypatch):
    bad = ("```python\nfrom modern.m7 import main\n\n"
           "def test_ok():\n    assert main('') == 'Z'\n\n"
           "def test_wrong_guess():\n    assert main('') == 'nope'\n```")
    monkeypatch.setattr(_llm, "call_llm", lambda *a: bad)     # repair returns the same file
    src = test_writer.write_unit_tests({"module_id": "m7"}, "def main(s):\n    return 'Z'\n")
    assert "test_ok" in src and "test_wrong_guess" not in src


def test_test_writer_accepts_passing_tests_without_repair(monkeypatch):
    good = "```python\nfrom modern.m8 import main\n\ndef test_ok():\n    assert main('') == 'Z'\n```"
    calls = []
    monkeypatch.setattr(_llm, "call_llm", lambda *a: (calls.append(1), good)[1])
    test_writer.write_unit_tests({"module_id": "m8"}, "def main(s):\n    return 'Z'\n")
    assert len(calls) == 1


def test_fallback_skips_retired_model(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "x")
    monkeypatch.setattr(_llm, "MODEL_CHAINS", {"nano": ["dead/model", "live/model"]})
    monkeypatch.setattr(_llm, "_dead_models", set())
    tried = []
    def fake_one(model_id, s, u, thinking):
        tried.append(model_id)
        if model_id == "dead/model":
            raise _llm._ModelUnavailable("[410] Gone")
        return "OK", "r"
    monkeypatch.setattr(_llm, "_invoke_one", fake_one)
    assert _llm._invoke("nano", "s", "u") == ("OK", "r", "live/model")
    assert _llm._invoke("nano", "s", "u")[2] == "live/model"
    assert tried == ["dead/model", "live/model", "live/model"]  # dead model not retried


def test_empty_answer_after_reasoning_retries_without_thinking(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "x")
    monkeypatch.setattr(_llm, "MODEL_CHAINS", {"super": ["m"]})
    monkeypatch.setattr(_llm, "_dead_models", set())
    modes = []
    def fake_one(model_id, s, u, thinking):
        modes.append(thinking)
        return ("", "long reasoning...") if thinking else ("ANSWER", "")
    monkeypatch.setattr(_llm, "_invoke_one", fake_one)
    assert _llm._invoke("super", "s", "u")[0] == "ANSWER"
    assert modes == [True, False]
