"""Person 2's shared-contract entry points for running original COBOL."""

from .runtime import (
    CobolCompileError,
    CobolRunError,
    LegacyError,
    compile_cobol,
    record_golden,
    run_cobol,
)

__all__ = [
    "compile_cobol", "run_cobol", "record_golden",
    "LegacyError", "CobolCompileError", "CobolRunError",
]
