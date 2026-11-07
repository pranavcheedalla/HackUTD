"""Agents package.

Contract entry points (P4): rewrite, write_unit_tests, explain_divergence.
P3 adds understand / extract_spec / generate_inputs here at merge time.
"""
from agents.rewrite import rewrite
from agents.test_writer import write_unit_tests
from agents.explainer import explain_divergence

__all__ = ["rewrite", "write_unit_tests", "explain_divergence"]
