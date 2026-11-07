"""Offline stand-in for call_llm: canned but schema-shaped replies built from the static analysis."""
from __future__ import annotations

import re

from agents.cobol_static import analyze

CALLS: list[dict] = []


def _source_from_prompt(user: str) -> str:
    part = user.split("COBOL SOURCE", 1)[-1]
    return "\n".join(m.group(1) for m in re.finditer(r"^\s*\d+\| ?(.*)$", part, re.M))


def fake_call_llm(model, system, user, json_schema=None):
    CALLS.append({"model": model, "system": system, "user": user})
    a = analyze(_source_from_prompt(user))
    if "cases" in (json_schema or {}).get("properties", {}):
        w = a.input_width or 10
        cases = [{"input": str(i).zfill(w)[-w:], "covers": f"fake case {i}"} for i in range(1, 26)]
        cases.append({"input": cases[0]["input"], "covers": "duplicate - should be dropped"})
        return {"cases": cases}
    mid = re.search(r'module_id "([^"]+)"', user).group(1)
    return {
        "module_id": mid,
        "summary": f"Fake offline spec for {mid}.",
        "inputs": [{"name": f["name"], "type": "decimal", "format": f"cols {f['start']}-{f['end']}"}
                   for f in a.input_layout] or [{"name": "none", "type": "string", "format": "LINKAGE"}],
        "outputs": [{"name": f"line{i}", "type": "string", "format": t} for i, (_, t) in enumerate(a.displays, 1)]
                   or [{"name": "none", "type": "string", "format": "LINKAGE"}],
        "business_rules": ["fake rule"],
        "edge_cases": ["fake edge case"],
        "quirks": [],  # deliberately empty: the static safety net must add the truncation
    }
