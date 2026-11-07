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
