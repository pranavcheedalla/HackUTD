"""
P3 — Understanding agents. STUB VERSION until P3's real code is merged.
Real versions call llm.call_llm("nano"/"super", ...).
"""
from __future__ import annotations

import re
from pathlib import Path

STUB = True


def understand(legacy_dir: str) -> list[dict]:
    """Find .cbl files and CALL/COPY deps. Return modules ordered leaves first."""
    files = sorted(Path(legacy_dir).glob("*.cbl"))
    mods = []
    for f in files:
        src = f.read_text(errors="ignore")
        deps = re.findall(r"CALL\s+'([A-Z0-9-]+)'", src, flags=re.I)
        mods.append({"module_id": f.stem.lower(), "cobol_path": str(f),
                     "depends_on": [d.lower() for d in deps]})
    # leaves first: fewer deps first (P3 replaces with a real topological sort)
    return sorted(mods, key=lambda m: len(m["depends_on"]))


def extract_spec(cobol_src: str) -> dict:
    m = re.search(r"PROGRAM-ID\.\s*([A-Z0-9-]+)", cobol_src, flags=re.I)
    mid = m.group(1).lower() if m else "unknown"
    return {
        "module_id": mid,
        "summary": f"[stub] Reads one line and echoes it upper-cased with an OUT: prefix.",
        "inputs": [{"name": "line", "type": "string", "format": "free text"}],
        "outputs": [{"name": "result", "type": "string", "format": "OUT:<UPPERCASE INPUT>"}],
        "business_rules": ["Output is 'OUT:' followed by the trimmed input in upper case"],
        "edge_cases": ["empty input", "mixed case", "digits"],
        "quirks": [],
    }


def generate_inputs(spec: dict, cobol_src: str) -> list[str]:
    return ["hello", "Mixed Case", "12345", "", "  padded  ", "zero 0"]
