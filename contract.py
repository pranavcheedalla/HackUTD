"""
Shared contract. Every teammate codes against these types and signatures.
Do NOT change a signature without telling Hemant (he owns merges).

COBOL I/O convention: every program reads ONE line of input from stdin (ACCEPT)
and writes output with DISPLAY. No files or databases.

Owners:
  P1 (Hemant)  llm.py, pipeline/, run.py
  P2           legacy.py, testing.py, legacy/*.cbl, golden/
  P3           agents/understanding.py  (understand, extract_spec, generate_inputs)
  P4           agents/building.py       (rewrite, write_unit_tests, explain_divergence)
"""
from __future__ import annotations

from typing import Literal, Optional, TypedDict


# ---------- Data shapes ----------

class Field(TypedDict):
    name: str
    type: str      # e.g. "decimal", "integer", "string"
    format: str    # e.g. "PIC 9(5)V99", "zero-padded 7 digits"


class Spec(TypedDict):
    module_id: str
    summary: str
    inputs: list[Field]
    outputs: list[Field]
    business_rules: list[str]
    edge_cases: list[str]
    quirks: list[str]          # truncation, rounding, overflow, etc.


class GoldenCase(TypedDict):   # one line of golden/<module_id>.jsonl
    input: str
    output: str


class Failure(TypedDict):
    input: str
    expected: str
    actual: str


class TestResult(TypedDict):
    passed: int
    total: int
    failures: list[Failure]


class Divergence(TypedDict):
    verdict: Literal["new_code_bug", "legacy_quirk"]
    reason: str
    input: str
    expected: str
    actual: str


class ModuleInfo(TypedDict):   # returned by agents.understand
    module_id: str
    cobol_path: str
    depends_on: list[str]


Status = Literal["pending", "spec", "recorded", "rewriting",
                 "verifying", "done", "failed"]


class ModuleState(TypedDict, total=False):
    id: str
    cobol_path: str
    spec: Optional[Spec]
    golden_path: Optional[str]
    py_path: Optional[str]
    status: Status
    attempts: int
    tests_passed: int
    tests_total: int
    divergences: list[Divergence]
    last_failures: list[Failure]
    error: Optional[str]


# ---------- JSON schema for Spec (used by llm.call_llm validation) ----------

SPEC_SCHEMA: dict = {
    "type": "object",
    "required": ["module_id", "summary", "inputs", "outputs",
                 "business_rules", "edge_cases", "quirks"],
    "properties": {
        "module_id": {"type": "string"},
        "summary": {"type": "string"},
        "inputs": {"type": "array", "items": {"type": "object",
                   "required": ["name", "type", "format"]}},
        "outputs": {"type": "array", "items": {"type": "object",
                    "required": ["name", "type", "format"]}},
        "business_rules": {"type": "array", "items": {"type": "string"}},
        "edge_cases": {"type": "array", "items": {"type": "string"}},
        "quirks": {"type": "array", "items": {"type": "string"}},
    },
}

DIVERGENCE_SCHEMA: dict = {
    "type": "object",
    "required": ["verdict", "reason"],
    "properties": {
        "verdict": {"enum": ["new_code_bug", "legacy_quirk"]},
        "reason": {"type": "string"},
    },
}


# ---------- Function signatures (implementations live in the owner's file) ----------
#
# P1  llm.call_llm(model: "nano"|"super", system: str, user: str, json_schema: dict|None) -> dict|str
# P2  legacy.compile_cobol(cobol_path: str) -> str                       # binary path
# P2  legacy.run_cobol(binary_path: str, input_line: str) -> str         # exact stdout, trailing newline stripped
# P2  legacy.record_golden(module_id: str, binary_path: str, inputs: list[str]) -> str   # golden path
# P2  testing.golden_to_pytest(module_id: str, py_module_path: str) -> str               # test path
# P2  testing.run_equivalence(module_id: str) -> TestResult
# P3  agents.understand(legacy_dir: str) -> list[ModuleInfo]             # ordered leaves first
# P3  agents.extract_spec(cobol_src: str) -> Spec
# P3  agents.generate_inputs(spec: Spec, cobol_src: str) -> list[str]
# P4  agents.rewrite(spec: Spec, cobol_src: str, failures: list[Failure] | None) -> str   # python source
# P4  agents.write_unit_tests(spec: Spec, python_src: str) -> str        # pytest source
# P4  agents.explain_divergence(spec, cobol_src, python_src, failure: Failure) -> {"verdict", "reason"}
#
# Rewritten Python modules MUST expose:  def main(input_line: str) -> str
# Money uses decimal.Decimal. Every LLM call goes through llm.call_llm.


# ======================================================================================
# CODEBASE SUPPORT (multi-file COBOL: copybooks + CALL).  Frozen 2026-11-07, see
# docs/codebase-support-plan.md.  Owners build against these; do not change alone.
# Acceptance tests: tests/codebase/  (CODEBASE_MERGE=1 turns "pending" skips into failures)
# ======================================================================================

class Param(TypedDict):
    """One LINKAGE SECTION parameter of a subprogram, in PROCEDURE DIVISION USING order."""
    name: str          # "LK-RATE"
    pic: str           # "9(2)V99", "X", "S9(7)V99"
    kind: Literal["numeric", "text"]
    int_digits: int    # numeric: digits before the implied point; text: 0
    dec_digits: int    # numeric: digits after the implied point; text: 0
    length: int        # text: characters; numeric: int_digits + dec_digits
    signed: bool


class CodebaseModule(ModuleInfo, total=False):
    """Extra keys agents.understand returns per module (all modules, old keys unchanged)."""
    program_id: str
    kind: Literal["program", "subprogram"]   # subprogram = PROCEDURE DIVISION USING ...
    copy_dirs: list[str]                     # absolute dirs holding its copybooks (cobc -I)
    link: list[str]                          # absolute .cbl paths of every callee, transitively,
                                             # callees-first, excluding the module itself
    params: list[Param]                      # subprograms only; [] for programs


class DepInfo(TypedDict):
    """What the rewrite agent gets for each already-verified callee."""
    module_id: str      # also its Python module name: `import <module_id>`
    program_id: str     # COBOL name used in CALL 'NAME'
    python_src: str     # accepted modern/<module_id>.py
    params: list[Param]


# P2  legacy.compile_program(cobol_path: str, link: list[str] = (), copy_dirs: list[str] = (),
#                            source_format: "auto"|"free"|"fixed" = "auto") -> str   # binary path
#       Compiles cobol_path as the main program plus every file in `link` as called
#       subprograms, each in its own detected format ("auto": try free, then fixed),
#       with every copy_dirs entry on the copybook path. compile_cobol(p) keeps working.
#
# P3  agents.make_driver(subprogram_src: str) -> str          # free-format COBOL source
#       Driver PROGRAM-ID is "DRV-<PROGRAM-ID>". It ACCEPTs one line, UNSTRINGs it on "|" into
#       the params in USING order (numeric via FUNCTION NUMVAL, text MOVEd as-is), CALLs the
#       subprogram, and DISPLAYs ONE line:  NAME=value|NAME=value|...  for every param after
#       the call. Numeric values are shown as PIC 9(i).9(d) (zero-padded, "9(i)" if d = 0,
#       leading "-" form "-9(i).9(d)" if signed); text values as stored (fixed length).
#       Reference: tests/fixtures/codebase/drivers/discount_driver.cbl
#
# P3  agents.generate_inputs(spec, cobol_src) for a subprogram returns DRIVER-format lines.
#
# P4  agents.rewrite(spec, cobol_src, failures=None, previous_src=None,
#                    deps: list[DepInfo] | None = None) -> str
#       Every module exposes main(input_line) -> str. A subprogram's main() uses the driver
#       format above, and it ALSO exposes call(*params) -> tuple (all params after the call;
#       Decimal for numeric, str for text). A caller imports each callee by module_id and uses
#       <module_id>.call(...). Reference: tests/fixtures/codebase/modern/*.py
#
# P1  pipeline: compile with link/copy_dirs; subprograms are recorded through make_driver;
#     rewrite gets deps for every depends_on module; a module whose dependency is not "done"
#     fails with error "blocked: dependency <id> not verified". run.py/isolated_run accept any
#     legacy dir (python tools/isolated_run.py --mode real --legacy-dir samples/legacy).
