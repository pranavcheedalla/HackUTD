"""Single place the understanding agents get call_llm from.

Uses Hemant's real llm.call_llm once it is merged; until then falls back to the
temporary llm_local stand-in. Nothing else in agents/ needs to change at merge time.
"""
from __future__ import annotations

try:
    from llm import call_llm  # P1's real wrapper (retries, caching, schema repair)
except ModuleNotFoundError as exc:  # only fall back if the module itself is missing
    if exc.name != "llm":
        raise
    from llm_local import call_llm  # TEMPORARY - delete llm_local.py after Merge 1

__all__ = ["call_llm"]
