"""
P3 — Understanding agents (real version). The code lives in the modules below;
this file keeps the import path the pipeline already uses (agents/__init__.py).

    understand(legacy_dir)            -> modules, leaves first     (no LLM: regex + topo sort)
    extract_spec(cobol_src)           -> Spec dict                 (Nemotron Nano)
    generate_inputs(spec, cobol_src)  -> list[str] stdin records   (Nemotron Super)

Pass copybook-expanded source: load_cobol_source(module["cobol_path"]). See P3_NOTES.md.
"""
from __future__ import annotations

from .understand import understand, load_cobol_source  # noqa: F401
from .extract_spec import extract_spec  # noqa: F401
from .generate_inputs import generate_inputs  # noqa: F401

