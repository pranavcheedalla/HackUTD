"""Shared helpers for the codebase-support acceptance tests (see docs/codebase-support-plan.md).

A test marks work that has not landed yet as "pending" (skipped). At merge time run
    CODEBASE_MERGE=1 python -m pytest -q tests/codebase
and every pending item becomes a FAILURE, so nothing unfinished can hide.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples" / "legacy"
FIXTURES = ROOT / "tests" / "fixtures" / "codebase"
INPUTS = json.loads((FIXTURES / "inputs.json").read_text())


def pending(owner: str, what: str):
    message = f"pending ({owner}): {what}"
    if os.getenv("CODEBASE_MERGE") == "1":
        pytest.fail(message)
    pytest.skip(message)


def call_or_pending(owner: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except NotImplementedError as error:
        pending(owner, str(error))


def reference(module_id: str):
    """Hand-written reference Python for a sample module (verified against real COBOL)."""
    folder = str(FIXTURES / "modern")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    spec = importlib.util.spec_from_file_location(module_id, FIXTURES / "modern" / f"{module_id}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_id] = module
    spec.loader.exec_module(module)
    return module


def run_binary(binary: str, line: str) -> str:
    out = subprocess.run([binary], input=line + "\n", capture_output=True, text=True, timeout=10)
    assert out.returncode == 0, out.stderr
    return out.stdout[:-1] if out.stdout.endswith("\n") else out.stdout


needs_cobc = pytest.mark.skipif(shutil.which("cobc") is None, reason="GnuCOBOL (cobc) not installed")
