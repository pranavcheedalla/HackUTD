"""P4 · Rewrite agent: spec + COBOL -> standalone Python module with main(input_line) -> str.

Contract: rewrite(spec, cobol_src, failures: list|None) -> python_src
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from agents import _llm

HELPERS_SRC = (Path(__file__).parent / "cobol_helpers.py").read_text()
HELPER_NAMES = ("pic_store", "pic_from_text", "split_fixed", "display_num", "edit_picture")
MAX_FAILURES_IN_PROMPT = 8

# ----------------------------------------------------------------------------- prompts
REWRITE_SYSTEM = """You are a senior engineer migrating COBOL programs to Python 3.11.
Your Python must produce output that is BYTE-FOR-BYTE IDENTICAL to the COBOL program's
DISPLAY output for every input, including legacy quirks. Equivalence beats elegance.

Program I/O convention: the COBOL program ACCEPTs exactly ONE line from stdin and writes
with DISPLAY. Your module must define:

    def main(input_line: str) -> str

which returns everything the COBOL program would print, with lines joined by "\\n" and
NO trailing newline. No stdin/stdout, no files, no network, no randomness, no globals that
keep state between calls.

COBOL semantics you MUST replicate (GnuCOBOL defaults):
1. Money and all PIC 9 numbers use decimal.Decimal. Never float.
2. Storing into a PIC field (MOVE, COMPUTE, ADD, MULTIPLY...) TRUNCATES extra decimal
   places unless the statement says ROUNDED. It also silently drops high-order digits that
   don't fit (no ON SIZE ERROR). Unsigned fields (no S) lose the minus sign.
   Apply this at EVERY store, in the same order the COBOL does, not just at the end.
3. Intermediate results inside one COMPUTE expression keep full precision; truncation only
   happens when stored into the target field.
4. ACCEPT into a group item splits the line by fixed column widths from the PIC sizes
   (short input padded with spaces). A PIC 9(5)V99 input field is 7 digits with an
   IMPLIED decimal point: "0012345" -> 123.45.
5. DISPLAY of an un-edited numeric field prints all digits with leading zeros and a "."
   for the implied decimal (PIC 9(3)V99 = 1.5 -> "001.50"); signed fields get a leading
   "+" or "-". DISPLAY of an alphanumeric PIC X(n) field prints it padded to n chars.
6. Numeric-EDITED pictures (Z, comma, period, $, -, CR...) suppress leading zeros with spaces
   and keep a fixed width. Reproduce the width exactly.
7. DISPLAY "A" B "C" concatenates items with NO separator. Each DISPLAY statement is one line.

You may use these tested helpers. If you call them, copy them verbatim into your module
OR just call them by name and they will be inlined automatically:

```python
{helpers}
```

Write idiomatic, readable Python: a small dataclass or named fields for the input record,
one function per COBOL paragraph where it helps, and short comments that name the COBOL
field/paragraph each piece comes from. Comment every place where you deliberately copy a
legacy quirk (e.g. "# COBOL truncates here, not rounds").

Return ONLY the complete Python module in a single ```python code block."""

REWRITE_USER = """Module id: {module_id}

## Spec (from the analysis agent)
{spec}

## Original COBOL
```cobol
{cobol}
```
{fix_section}
Write the complete Python module now."""

FIX_SECTION = """
## Your previous Python version
```python
{previous}
```

## It FAILED these equivalence cases (expected = real COBOL output)
{failures}

Fix ONLY what is wrong. Compare expected vs actual character by character: look for
truncation vs rounding, field widths, leading zeros/spaces, sign handling, and digits
lost to field overflow. Keep everything that already works unchanged.
"""

SYNTAX_FIX_USER = """Your module is invalid: {error}

Return the complete corrected module in a single ```python code block.

```python
{code}
```"""

# ----------------------------------------------------------------------------- agent
_last_src: dict[str, str] = {}  # module_id -> most recent rewrite (for fix-only-what's-wrong)


def rewrite(spec: dict, cobol_src: str, failures: list | None = None, previous_src: str | None = None) -> str:
    """Return Python source for the module. `previous_src` is optional; if omitted on a
    retry, the last rewrite produced for this module_id in this process is used."""
    module_id = spec.get("module_id", "module")
    fix_section = ""
    if failures:
        prev = previous_src or _last_src.get(module_id)
        fix_section = FIX_SECTION.format(
            previous=prev or "(not available — rewrite from scratch)",
            failures=format_failures(failures),
        )

    system = REWRITE_SYSTEM.replace("{helpers}", HELPERS_SRC)
    user = REWRITE_USER.format(
        module_id=module_id,
        spec=json.dumps(spec, indent=2),
        cobol=cobol_src,
        fix_section=fix_section,
    )
    code = finalize(extract_code(_llm.call_llm("super", system, user, None)))

    err = validate(code)
    if err:  # one retry with the error
        code = finalize(
            extract_code(_llm.call_llm("super", system, SYNTAX_FIX_USER.format(error=err, code=code), None))
        )
        err = validate(code)
        if err:
            print(f"[rewrite] {module_id}: still invalid after retry: {err}")

    _last_src[module_id] = code
    return code


# ----------------------------------------------------------------------------- helpers
def format_failures(failures: list) -> str:
    lines = []
    for i, f in enumerate(failures[:MAX_FAILURES_IN_PROMPT], 1):
        lines.append(
            f"Case {i}\n  input:    {f.get('input')!r}\n"
            f"  expected: {f.get('expected')!r}\n  actual:   {f.get('actual')!r}"
        )
    if len(failures) > MAX_FAILURES_IN_PROMPT:
        lines.append(f"... and {len(failures) - MAX_FAILURES_IN_PROMPT} more failing cases")
    return "\n".join(lines)


def extract_code(text) -> str:
    text = _llm.strip_thinking(str(text))
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text, flags=re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    return text.strip() + "\n"


def finalize(code: str) -> str:
    """Inline cobol_helpers if the code uses them without defining them, and drop any
    import of the helpers module so the generated file is standalone."""
    code = re.sub(r"^\s*(from\s+(agents\.)?cobol_helpers\s+import[^\n]*|import\s+(agents\.)?cobol_helpers[^\n]*)\n",
                  "", code, flags=re.MULTILINE)
    used = [n for n in HELPER_NAMES if re.search(rf"\b{n}\s*\(", code)]
    missing = [n for n in used if not re.search(rf"^def {n}\s*\(", code, flags=re.MULTILINE)]
    if missing:
        helpers_body = HELPERS_SRC.split('"""', 2)[2].lstrip()  # drop module docstring
        helpers_body = re.sub(r"^HELPER_NAMES = .*\n?", "", helpers_body, flags=re.MULTILINE)
        code = "# --- COBOL data semantics helpers (inlined) ---\n" + helpers_body.rstrip() + \
               "\n# --- end helpers ---\n\n" + code
        code = _hoist_future_imports(code)
    return code


def _hoist_future_imports(code: str) -> str:
    futures = re.findall(r"^from __future__ import[^\n]*\n", code, flags=re.MULTILINE)
    if not futures:
        return code
    code = re.sub(r"^from __future__ import[^\n]*\n", "", code, flags=re.MULTILINE)
    return "".join(dict.fromkeys(futures)) + code


def validate(code: str) -> str | None:
    """Return an error message, or None if the module looks usable."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"
    mains = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
    if not mains:
        return "module must define a top-level function `def main(input_line: str) -> str`"
    if len(mains[0].args.args) != 1:
        return "main must take exactly one argument: input_line"
    # stdin/stdout only allowed in an `if __name__ == "__main__":` block, never inside functions
    for fn in (n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))):
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("input", "print"):
                return f"`{fn.name}` must not call input()/print(); main returns the output string"
    return None
