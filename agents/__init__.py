"""Re-exports so the pipeline can do `import agents; agents.rewrite(...)`."""
from .understanding import understand, extract_spec, generate_inputs  # P3
from .building import rewrite, write_unit_tests, explain_divergence   # P4

__all__ = ["understand", "extract_spec", "generate_inputs",
           "rewrite", "write_unit_tests", "explain_divergence"]
