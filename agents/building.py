"""
P4 — Building agents (REAL, Nemotron-powered). Replaces the stub version.

The pipeline calls these through `agents/__init__.py`:
    agents.rewrite(spec, cobol_src, failures)                       -> python_src
    agents.write_unit_tests(spec, python_src)                       -> test_src
    agents.explain_divergence(spec, cobol_src, python_src, failure) -> {verdict, reason}

Implementations live one file per agent:
    agents/rewrite.py       Nemotron Super rewrite + sandboxed self-check/repair loop
    agents/test_writer.py   Nemotron Super unit tests, run in a sandbox, wrong ones dropped
    agents/explainer.py     Nemotron Super verdict + deterministic diff evidence/fallback
All model calls go through llm.call_llm (via agents/_nemotron.py, which adds tracing to
runs/nemotron_trace.jsonl). Offline tests: pytest dev/p4 -q
"""
from __future__ import annotations

from agents.explainer import explain_divergence
from agents.rewrite import rewrite
from agents.test_writer import write_unit_tests

STUB = False

__all__ = ["rewrite", "write_unit_tests", "explain_divergence"]
