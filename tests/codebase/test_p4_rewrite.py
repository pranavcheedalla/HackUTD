"""P4 (Pranav): rewrite() gets verified callees as `deps`; generated callers import them; subprograms expose call()."""
import importlib
import inspect

import pytest

from cbhelpers import FIXTURES, SAMPLES, pending, reference

OWNER = "P4 Pranav, agents/rewrite.py + _sandbox.py"
rw = importlib.import_module("agents.rewrite")


def _params():
    from test_p3_analysis import DISCOUNT_PARAMS
    return DISCOUNT_PARAMS


def _discount_dep():
    return {"module_id": "discount", "program_id": "DISCOUNT", "params": _params(),
            "python_src": (FIXTURES / "modern" / "discount.py").read_text()}


@pytest.fixture
def fake_model(monkeypatch):
    """Model stub: records every prompt and answers with a canned module."""
    calls = []

    def install(answer: str):
        def call_llm(model, system, user, schema=None):
            calls.append(system + "\n" + user)
            return f"```python\n{answer}\n```"
        monkeypatch.setattr(rw._llm, "call_llm", call_llm)
        return calls
    if "deps" not in inspect.signature(rw.rewrite).parameters:
        pending(OWNER, "rewrite(..., deps=None) parameter")
    return install


def test_caller_prompt_contains_dependency_and_sandbox_can_import_it(fake_model):
    calls = fake_model((FIXTURES / "modern" / "invoice.py").read_text())
    code = rw.rewrite({"module_id": "invoice"}, (SAMPLES / "invoice.cbl").read_text(), deps=[_discount_dep()])
    assert "import discount" in code
    assert len(calls) == 1, "self-check failed: the sandbox must make dependency modules importable"
    prompt = calls[0]
    assert "def call(" in prompt and "discount.call" in prompt
    assert "LK-SUBTOTAL" in prompt and "CALL 'DISCOUNT'" in prompt.upper().replace('"', "'")


def test_subprogram_prompt_states_call_and_driver_conventions(fake_model):
    calls = fake_model((FIXTURES / "modern" / "discount.py").read_text())
    code = rw.rewrite({"module_id": "discount"}, (SAMPLES / "discount.cbl").read_text())
    assert "def call(" in code and "def main(" in code
    assert len(calls) == 1
    assert "def call(" in calls[0] and "NAME=value" in calls[0]


def test_retry_keeps_dependencies_in_the_prompt(fake_model):
    calls = fake_model((FIXTURES / "modern" / "invoice.py").read_text())
    failure = {"input": "00020050000G", "expected": "x", "actual": "y"}
    rw.rewrite({"module_id": "invoice"}, (SAMPLES / "invoice.cbl").read_text(), failures=[failure],
               deps=[_discount_dep()])
    assert "discount.call" in calls[0]


def test_no_deps_still_works_for_standalone_programs(fake_model):
    ref = reference("interest")
    calls = fake_model((FIXTURES / "modern" / "interest.py").read_text())
    code = rw.rewrite({"module_id": "interest"}, (SAMPLES / "interest.cbl").read_text(), deps=None)
    assert "def main(" in code and len(calls) == 1 and ref.main("") == "ERROR: YEARS MUST BE AT LEAST 1"
