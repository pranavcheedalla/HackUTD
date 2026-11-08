"""P4 · Rewrite agent (Nemotron 3 Super): spec + COBOL -> standalone Python module
with main(input_line) -> str.

Contract: rewrite(spec, cobol_src, failures=None, previous_src=None, deps=None) -> python_src
  deps (codebase support): verified callees to IMPORT; subprograms also get call(*params).

Loop inside one rewrite() call (max P4_REWRITE_CALLS Nemotron calls, default 3):
  Nemotron writes the module -> static check (syntax, main signature, no print/input)
  -> sandbox run (no crash on any failing input or blank input)
  -> replay the failing cases we were given: still wrong? feed the new diff back to Nemotron.
The best candidate seen is returned, so the pipeline's verify step gets the strongest attempt.
"""
from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

from agents import _nemotron as _llm, _sandbox

HELPERS_SRC = (Path(__file__).parent / "cobol_helpers.py").read_text()
HELPER_NAMES = ("pic_store", "pic_from_text", "split_fixed", "display_num", "edit_picture")
MAX_FAILURES_IN_PROMPT = 8
MAX_LLM_CALLS = int(os.environ.get("P4_REWRITE_CALLS", "3"))
SMOKE_INPUTS = [""]  # COBOL never crashes on short input (ACCEPT pads with spaces); Python mustn't either

# ----------------------------------------------------------------------------- prompts
REWRITE_SYSTEM = """You are a senior engineer migrating COBOL programs to Python 3.11.
Your Python must produce output that is BYTE-FOR-BYTE IDENTICAL to the COBOL program's
DISPLAY output for every input, including legacy quirks. Equivalence beats elegance.

Program I/O convention: the COBOL program ACCEPTs exactly ONE line from stdin and writes
with DISPLAY. Your module must define:

    def main(input_line: str) -> str

which returns everything the COBOL program would print, with lines joined by "\\n" and
NO trailing newline. main must never raise (COBOL doesn't crash on odd input). No
stdin/stdout inside functions, no files, no network, no randomness, no state kept
between calls. An `if __name__ == "__main__":` block is allowed.

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
   IMPLIED decimal point: "0012345" -> 123.45. UNSTRING ... DELIMITED BY SPACE splits on
   spaces; FUNCTION NUMVAL parses a human-readable number like "123.45".
5. DISPLAY of an un-edited numeric field prints all digits with leading zeros and a "."
   for the implied decimal (PIC 9(3)V99 = 1.5 -> "001.50"); signed fields get a leading
   "+" or "-". DISPLAY of an alphanumeric PIC X(n) field prints it padded to n chars.
6. In numeric-EDITED pictures, Z suppresses zeros with spaces. A 9 preserves each digit:
   PIC 9(7).99 prints 100.00 as "0000100.00". Reproduce the exact width.
7. DISPLAY "A" B "C" concatenates items with NO separator. Each DISPLAY statement is one line.
8. Preserve validation and control flow BEFORE NUMVAL or PIC storage. Do not normalize
   malformed input into a valid number. UNSTRING uses its literal delimiter, including '|'.
9. COBOL paragraphs share working-storage state. A validity flag initialized once and set
   to 0 stays 0 across later PERFORM calls unless COBOL explicitly resets it. A valid second
   field must never erase a failure in the first field. Every invalid character must remain
   invalid, even if final digit counts look valid. Prefer an early error return or accumulate
   validity with AND; never reset an invalid flag to 1 at the end of a validator.
10. The source and actual failing-case outputs take precedence over any draft-spec mistake.
11. FUNCTION TRIM removes ASCII spaces only. Use strip(' '), never bare strip(): tabs and
   other whitespace remain characters and may be rejected by validation. ACCEPT into
   PIC X(256) also limits the input buffer before inspecting or splitting delimiters.
12. ON SIZE ERROR overrides rule 2. For COMPUTE/ADD/SUBTRACT/MULTIPLY/DIVIDE ... ON SIZE ERROR,
   compute the full-precision result first; if its integer part needs more digits than the
   target PIC holds, run the ON SIZE ERROR branch and do NOT store or truncate. Only
   statements WITHOUT ON SIZE ERROR silently drop high-order digits.

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
{context_sections}{fix_section}
Write the complete Python module now."""

COPYBOOK_SECTION = """
## Copybooks (the text each COPY statement pulls in)
{copybooks}
"""

DEPS_SECTION = """
## Already-verified dependencies: IMPORT them, never re-implement them
This program CALLs other COBOL programs that are already migrated and proven identical to
the legacy code. Each one is a Python module that exposes:

    def call(*params) -> tuple   # params in USING order; returns EVERY param after the call

Rules:
- Put `import <module_id>` at the top of your module and use `<module_id>.call(...)`.
- Do NOT copy, inline or re-implement the dependency's logic.
- Pass arguments in the CALL ... USING order: Decimal for numeric params, str for text.
- COBOL passes BY REFERENCE, so the callee may change any argument: unpack the returned
  tuple back into your variables, e.g. `tier, subtotal, rate = discount.call(tier, subtotal, rate)`.
- After the call, keep the caller's own PIC truncation when it MOVEs/COMPUTEs the results.
{deps}
"""

DEP_ENTRY = """
### CALL '{program_id}'  ->  `import {module_id}` and `{module_id}.call(...)`
Parameters (USING order):
{params}
Verified Python of `{module_id}` (for reference only, do not copy it):
```python
{python_src}
```
"""

SUBPROGRAM_SECTION = """
## This is a SUBPROGRAM (PROCEDURE DIVISION USING ...): it needs TWO entry points
A subprogram never ACCEPTs input or DISPLAYs output itself; its result is the value of its
LINKAGE parameters after it runs (COBOL passes them BY REFERENCE). Write both:

1. `def call({call_args}) -> tuple`
   Parameters in USING order ({using}). Numeric params are Decimal, text params are str.
   Return a tuple of EVERY parameter after the call, in the same order, even unchanged ones,
   with each value already stored per its PIC (truncated, fixed length for text).
   Other migrated programs will import this module and use call().

2. `def main(input_line: str) -> str`  (test-driver format, used for equivalence tests)
   Input: the params joined by "|" in USING order, numbers as decimal text
   (e.g. "G|100.00|0"). Parse numbers like FUNCTION NUMVAL and store them into their PIC,
   take text as-is cut/padded to its length. Call call(), then return ONE line
   `NAME=value|NAME=value|...` for every param after the call, using the COBOL names.
   Numeric values are zero-padded as 9(int).9(dec) ("9(int)" if no decimals, a leading "-"
   if signed and negative); text values exactly as stored (fixed length).
   Example: main("G|100.00|0") == "LK-TIER=G|LK-SUBTOTAL=0000100.00|LK-RATE=12.50"
"""

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

SELF_CHECK_SECTION = """
## Your previous Python version
```python
{previous}
```

## An automatic check of that version found this problem
{problem}

Fix it. Keep everything that already works unchanged.
"""


# ----------------------------------------------------------------------------- agent
_last_src: dict[str, str] = {}  # module_id -> most recent rewrite (for fix-only-what's-wrong)


def rewrite(spec: dict, cobol_src: str, failures: list | None = None, previous_src: str | None = None,
            deps: list | None = None) -> str:
    """Return Python source for the module.

    `previous_src`: optional; on a retry without it, the last rewrite of this module_id is used.
    `deps`: list[DepInfo] of already-verified callees ({module_id, program_id, params,
    python_src}). The rewrite imports them instead of re-implementing them. None/[] = standalone.
    """
    module_id = spec.get("module_id", "module")
    system = REWRITE_SYSTEM.replace("{helpers}", HELPERS_SRC)
    deps = list(deps or [])
    subprogram = is_subprogram(cobol_src)
    context_sections = build_context(cobol_src, deps, subprogram)  # kept on every retry

    fix_section = ""
    if failures:
        prev = previous_src or _last_src.get(module_id)
        fix_section = FIX_SECTION.format(
            previous=prev or "(not available, rewrite from scratch)",
            failures=format_failures(failures),
        )

    best: tuple[tuple, str] | None = None
    with _llm.agent("rewrite", module_id):
        for call in range(1, MAX_LLM_CALLS + 1):
            user = REWRITE_USER.format(module_id=module_id, spec=json.dumps(spec, indent=2),
                                       cobol=cobol_src, context_sections=context_sections,
                                       fix_section=fix_section)
            code = finalize(extract_code(_llm.call_llm("super", system, user, None)))
            problem, score = self_check(code, failures, deps, subprogram)
            if best is None or score < best[0]:
                best = (score, code)
            if problem is None:
                break
            print(f"[rewrite] {module_id}: Nemotron call {call} -> {problem.splitlines()[0]}")
            fix_section = SELF_CHECK_SECTION.format(previous=code, problem=problem)

    code = best[1]
    _last_src[module_id] = code
    return code


def self_check(code: str, failures: list | None, deps: list | None = None,
               subprogram: bool = False) -> tuple[str | None, tuple]:
    """Return (problem description or None, score). Lower score = better candidate.
    Dependencies are written next to the candidate in the sandbox so `import <dep>` works."""
    err = validate(code, subprogram=subprogram, local_modules=[d["module_id"] for d in deps or []])
    if err:
        return f"The module is invalid: {err}", (3, 0)
    for d in deps or []:
        if not re.search(rf"^\s*(import\s+{re.escape(d['module_id'])}\b|from\s+{re.escape(d['module_id'])}\s+import)",
                         code, flags=re.MULTILINE):
            return (f"The module must `import {d['module_id']}` and use {d['module_id']}.call(...) "
                    f"for CALL '{d.get('program_id', d['module_id'])}' instead of re-implementing it."), (3, 0)

    failures = failures or []
    inputs = [str(f.get("input", "")) for f in failures] + SMOKE_INPUTS
    modules = {d["module_id"]: d["python_src"] for d in deps or []}
    res = _sandbox.run_main(code, inputs, modules=modules)
    if "timeout" in res:
        return "main() did not finish within 20 seconds (infinite loop?).", (2, 0)
    if "import_error" in res:
        return f"Importing the module failed:\n{res['import_error']}", (2, 0)

    results = res["results"]
    crashes = [
        f"main({line!r}) " + (f"raised {r['error']}\n{r.get('trace', '')}" if not r["ok"] else "did not return a str")
        for line, r in zip(inputs, results)
        if not r["ok"] or not r.get("type_ok", True)
    ]
    if crashes:
        return "main() crashed:\n" + "\n".join(crashes[:5]), (1, len(crashes))

    still = [
        {"input": f.get("input"), "expected": f.get("expected"), "actual": r["output"]}
        for f, r in zip(failures, results)
        if r["output"] != f.get("expected")
    ]
    if still:
        return ("These equivalence cases still fail (expected = real COBOL output):\n"
                + format_failures(still)), (0, len(still))
    return None, (0, 0)


# ----------------------------------------------------------------------------- codebase support
_USING_RE = re.compile(r"PROCEDURE\s+DIVISION\s+USING\s+(.*?)\.", re.IGNORECASE | re.DOTALL)
_COPY_RE = re.compile(r"^[^*\n]{0,72}?\bCOPY\s+['\"]?([A-Z0-9][A-Z0-9_-]*)['\"]?", re.IGNORECASE | re.MULTILINE)
_REPO = Path(__file__).resolve().parent.parent
_COPY_EXTS = (".cpy", ".CPY", ".cbl", ".CBL", ".cob", ".COB", "")


def is_subprogram(cobol_src: str) -> bool:
    return bool(re.search(r"PROCEDURE\s+DIVISION\s+USING", cobol_src, re.IGNORECASE))


def using_params(cobol_src: str) -> list[str]:
    """LINKAGE names in PROCEDURE DIVISION USING order (BY REFERENCE/VALUE words dropped)."""
    m = _USING_RE.search(cobol_src)
    if not m:
        return []
    words = re.findall(r"[A-Z0-9][A-Z0-9-]*", m.group(1).upper())
    return [w for w in words if w not in ("BY", "REFERENCE", "VALUE", "CONTENT", "RETURNING")]


def build_context(cobol_src: str, deps: list, subprogram: bool) -> str:
    """Prompt sections that must be present on EVERY call, including retries."""
    out = ""
    copybooks = find_copybooks(cobol_src)
    if copybooks:
        out += COPYBOOK_SECTION.format(copybooks="\n".join(
            f"### COPY {name}\n```cobol\n{text.rstrip()}\n```" for name, text in copybooks.items()))
    if deps:
        out += DEPS_SECTION.format(deps="".join(
            DEP_ENTRY.format(program_id=d.get("program_id") or d["module_id"].upper(),
                             module_id=d["module_id"], params=format_params(d),
                             python_src=d.get("python_src", "").rstrip())
            for d in deps))
    if subprogram:
        names = using_params(cobol_src)
        args = ", ".join(n.lower().replace("-", "_") for n in names) or "*params"
        out += SUBPROGRAM_SECTION.format(call_args=args, using=", ".join(names) or "see COBOL")
    return out


def format_params(dep: dict) -> str:
    params = dep.get("params") or []
    if params:
        rows = ["| # | name | PIC | kind | digits (int.dec) / length | signed |",
                "|---|------|-----|------|---------------------------|--------|"]
        for i, p in enumerate(params, 1):
            size = (f"{p.get('int_digits', 0)}.{p.get('dec_digits', 0)}" if p.get("kind") == "numeric"
                    else f"{p.get('length', 0)} chars")
            rows.append(f"| {i} | {p.get('name')} | {p.get('pic')} | {p.get('kind')} | {size} | "
                        f"{'yes' if p.get('signed') else 'no'} |")
        return "\n".join(rows)
    # no param table given: fall back to the call() signature in its verified source
    try:
        for node in ast.parse(dep.get("python_src", "")).body:
            if isinstance(node, ast.FunctionDef) and node.name == "call":
                return f"`call({', '.join(a.arg for a in node.args.args)})` (see source below)"
    except SyntaxError:
        pass
    return "(see the call() signature in the source below)"


_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".cache", ".pytest_cache"}


def _repo_copy_dirs() -> list[Path]:
    out = []
    for root, dirnames, _ in os.walk(_REPO):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".venv"))
        out += [Path(root, d) for d in dirnames if d.lower() in ("copybooks", "copy", "cpy")]
    return out


def find_copybooks(cobol_src: str, search_dirs: list | None = None) -> dict[str, str]:
    """Text of every COPY'd member, so the model sees record layouts (e.g. INVREC).
    Looks in P4_COPY_DIRS (os.pathsep-separated), then any `copybooks`/legacy dir in the repo."""
    names = []
    for line in cobol_src.splitlines():
        if len(line) > 6 and line[6:7] in "*/" and not line.lstrip().startswith("COPY"):
            continue  # fixed-format comment line
        m = _COPY_RE.search(line)
        if m and m.group(1).upper() not in names:
            names.append(m.group(1).upper())
    if not names:
        return {}
    dirs = [Path(p) for p in (search_dirs or [])]
    dirs += [Path(p) for p in os.environ.get("P4_COPY_DIRS", "").split(os.pathsep) if p]
    dirs += _repo_copy_dirs()
    found = {}
    for name in names:
        for d in dirs:
            hit = next((d / (cand + ext) for cand in (name, name.lower()) for ext in _COPY_EXTS
                        if (d / (cand + ext)).is_file()), None)
            if hit:
                found[name] = hit.read_text(errors="replace")
                break
    return found


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


def validate(code: str, subprogram: bool = False, local_modules=()) -> str | None:
    """Return an error message, or None if the module looks usable.
    `local_modules`: verified dependency module ids the code may import."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"
    mains = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
    if not mains:
        return "module must define a top-level function `def main(input_line: str) -> str`"
    if len(mains[0].args.args) != 1:
        return "main must take exactly one argument: input_line"
    if subprogram and not any(isinstance(n, ast.FunctionDef) and n.name == "call" for n in tree.body):
        return ("this COBOL program is a subprogram (PROCEDURE DIVISION USING), so the module must "
                "also define a top-level `def call(*params) -> tuple` returning every param after the call")
    # stdin/stdout only allowed in an `if __name__ == "__main__":` block, never inside functions
    for fn in (n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))):
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("input", "print"):
                return f"`{fn.name}` must not call input()/print(); main returns the output string"
    from testing import rewrite_violations  # same rule the verify gate enforces
    problems = rewrite_violations(code, local_modules)
    if problems:
        return ("the module must compute its output from input_line alone (no files, no OS, "
                "no interpreter internals):\n" + "\n".join(problems[:5]))
    return None
