"""
P2 — Legacy runtime. STUB VERSION (fake data) until P2's real code is merged.

Real version: GnuCOBOL (`cobc -x`) compile + subprocess run.
The fake run_cobol upper-cases the input so the whole pipeline can run today.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLDEN_DIR = ROOT / "golden"

STUB = True  # P2: delete this flag when real code lands


def compile_cobol(cobol_path: str) -> str:
    """Compile a .cbl file. Returns the binary path."""
    return f"FAKE_BIN::{cobol_path}"


def run_cobol(binary_path: str, input_line: str) -> str:
    """Run the binary with one line on stdin. Returns stdout, trailing newline stripped."""
    return f"OUT:{input_line.strip().upper()}"


def record_golden(module_id: str, binary_path: str, inputs: list[str]) -> str:
    """Run every input and write golden/<module_id>.jsonl. Returns the path."""
    GOLDEN_DIR.mkdir(exist_ok=True)
    path = GOLDEN_DIR / f"{module_id}.jsonl"
    with path.open("w") as f:
        for line in inputs:
            f.write(json.dumps({"input": line, "output": run_cobol(binary_path, line)}) + "\n")
    return str(path)
