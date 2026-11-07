"""P4 · Unit-test writer agent (Nemotron 3 Super): spec + Python -> pytest source.

Contract: write_unit_tests(spec, python_src) -> test_src

Deliberately independent of the rewrite agent: it sees only the spec and the final code,
never the rewrite prompt or reasoning, so it can't inherit the same blind spots.
Generated tests import the module as `modern.<module_id>`.

After Nemotron writes the tests they are RUN in a sandbox against the code:
  - collection/import errors or failing tests -> one repair call with the pytest output
  - tests that still fail are removed (the code is already proven equal to COBOL by the
    golden tests, so a failing unit test here means the test's guess was wrong)
"""
from __future__ import annotations

import ast
import json
import re

from agents import _llm, _sandbox

# ----------------------------------------------------------------------------- prompts
TEST_WRITER_SYSTEM = """You are a QA engineer writing pytest unit tests for a Python module
that replaced a legacy COBOL program. You did NOT write the module, so don't trust it.

The module exposes:  main(input_line: str) -> str
Import it exactly like this:  from modern.{module_id} import main

Separate equivalence tests already compare main() with the real COBOL output, so your tests
focus on boundaries and error handling. Write tests that:
- feed boundary inputs from the spec: zero, max field sizes (all 9s), smallest non-zero,
  short/blank input, extra-long input, each business-rule branch
- assert properties you can be SURE of from the spec, for example:
  * main never raises on any of these inputs and always returns a str
  * output is deterministic (same input -> same output)
  * fixed-width output lines keep the same length across inputs
  * the error/validation branch is taken when the spec says it should (check for its text)
  * monotonic rules (e.g. more principal never yields less interest), when the spec implies them
- only assert an exact output value when you can compute it with certainty from the spec,
  and say how in a comment
- use @pytest.mark.parametrize for input lists; give each test a descriptive name

Rules: pytest and the standard library only. No network, files or randomness.
Return ONLY the test file in a single ```python code block."""

TEST_WRITER_USER = """## Spec
{spec}

## Module under test: modern/{module_id}.py
```python
{python_src}
```

Write tests/unit/test_{module_id}.py now."""

TEST_FIX_USER = """## Spec
{spec}

## Module under test: modern/{module_id}.py
```python
{python_src}
```

## Your test file
```python
{code}
```

## Problem
{problem}

The module's outputs are already verified identical to the legacy COBOL, so when a test
fails, the test's expectation is what's wrong: fix or loosen that assertion. Return the
complete corrected test file in a single ```python code block."""


# ----------------------------------------------------------------------------- agent
def write_unit_tests(spec: dict, python_src: str) -> str:
    module_id = spec.get("module_id", "module")
    system = TEST_WRITER_SYSTEM.replace("{module_id}", module_id)
    spec_json = json.dumps(spec, indent=2)

    # thinking off: test writing is mechanical, and with reasoning on Nemotron can spend its
    # whole token budget thinking (seen live: 38k chars of reasoning, empty answer)
    with _llm.agent("write_unit_tests", module_id, thinking=False):
        code = _extract(_llm.call_llm("super", system, TEST_WRITER_USER.format(
            spec=spec_json, module_id=module_id, python_src=python_src), None))

        problem, run = _check(code, module_id, python_src)
        if problem:
            print(f"[test_writer] {module_id}: repairing tests ({problem.splitlines()[0]})")
            fixed = _extract(_llm.call_llm("super", system, TEST_FIX_USER.format(
                spec=spec_json, module_id=module_id, python_src=python_src, code=code, problem=problem), None))
            fixed_problem, fixed_run = _check(fixed, module_id, python_src)
            if validate_tests(fixed, module_id) is None:
                code, problem, run = fixed, fixed_problem, fixed_run

    if run and run["failed"] and not run["collected_error"]:
        code = drop_tests(code, run["failed"])
        print(f"[test_writer] {module_id}: dropped wrong tests {run['failed']}")
    elif problem:
        print(f"[test_writer] {module_id}: tests still have problems: {problem.splitlines()[0]}")
    return code


def _check(code: str, module_id: str, python_src: str) -> tuple[str | None, dict | None]:
    err = validate_tests(code, module_id)
    if err:
        return err, None
    run = _sandbox.run_pytest(module_id, python_src, code)
    if run["ok"]:
        return None, run
    if run["collected_error"]:
        return "pytest could not run the file:\n" + run["output"], run
    return f"These tests fail: {', '.join(run['failed'])}\n" + run["output"], run


def _extract(text) -> str:
    text = _llm.strip_thinking(str(text))
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text, flags=re.DOTALL)
    return (max(blocks, key=len) if blocks else text).strip() + "\n"


def validate_tests(code: str, module_id: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"
    if not any(isinstance(n, ast.FunctionDef) and n.name.startswith("test_") for n in ast.walk(tree)):
        return "no test_ functions found"
    if f"modern.{module_id}" not in code:
        return f"tests must import main with: from modern.{module_id} import main"
    return None


def drop_tests(code: str, names: list[str]) -> str:
    """Remove top-level test functions (with their decorators) by name, keeping comments."""
    tree = ast.parse(code)
    lines = code.splitlines(keepends=True)
    spans = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            spans.append((start, node.end_lineno))
    for start, end in sorted(spans, reverse=True):
        del lines[start - 1 : end]
    return "".join(lines)
