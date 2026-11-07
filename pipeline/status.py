"""
Writes runs/state.json after every node so the dashboard can show live progress.

Shape:
{
  "run_id": "...", "started_at": "...", "updated_at": "...",
  "modules": { "<id>": ModuleState, ... },
  "events":  [ {"t": "...", "module": "<id>", "node": "rewrite", "msg": "..."} ]
}
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "runs" / "state.json"

_run: dict = {}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def start_run(module_ids: list[str]) -> None:
    global _run
    _run = {"run_id": uuid.uuid4().hex[:8], "started_at": _now(), "updated_at": _now(),
            "modules": {m: {"id": m, "status": "pending", "attempts": 0,
                            "tests_passed": 0, "tests_total": 0, "divergences": []}
                        for m in module_ids},
            "events": []}
    _flush()


def update(module: dict, node: str, msg: str = "") -> None:
    """Merge a module's latest state and log an event."""
    keep = {k: v for k, v in module.items() if k not in ("cobol_src", "python_src")}
    _run["modules"][module["id"]] = {**_run["modules"].get(module["id"], {}), **keep}
    _run["events"].append({"t": _now(), "module": module["id"], "node": node, "msg": msg})
    _run["updated_at"] = _now()
    _flush()


def _flush() -> None:
    # atomic write so the UI never reads a half-written file
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STATE_PATH.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(_run, f, indent=2, default=str)
    os.replace(tmp, STATE_PATH)


def set_mode(mode: str) -> None:
    """Expose whether the dashboard data came from fixtures or real model agents."""
    _run['mode'] = mode
    _flush()
