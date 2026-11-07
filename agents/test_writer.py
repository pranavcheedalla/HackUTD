"""P4 · Unit-test writer agent: spec + Python -> pytest source.

Contract: write_unit_tests(spec, python_src) -> test_src

Deliberately independent of the rewrite agent: it sees only the spec and the final code,
never the rewrite prompt or reasoning, so it can't inherit the same blind spots.
Generated tests import the module as `modern.<module_id>`.
"""
from __future__ import annotations

import ast
import json
import re

from agents import _llm

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

TEST_FIX_USER = """That test file is invalid: {error}
Return the complete corrected file in a single ```python code block.

```python
{code}
```"""


# ----------------------------------------------------------------------------- agent
def write_unit_tests(spec: dict, python_src: str) -> str:
    module_id = spec.get("module_id", "module")
    system = TEST_WRITER_SYSTEM.replace("{module_id}", module_id)
    user = TEST_WRITER_USER.format(spec=json.dumps(spec, indent=2), module_id=module_id, python_src=python_src)

    code = _extract(_llm.call_llm("super", system, user, None))
    err = validate_tests(code, module_id)
    if err:
        code = _extract(_llm.call_llm("super", system, TEST_FIX_USER.format(error=err, code=code), None))
        err = validate_tests(code, module_id)
        if err:
            print(f"[test_writer] {module_id}: still invalid after retry: {err}")
    return code


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
