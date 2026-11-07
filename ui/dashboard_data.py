"""Read dashboard artifacts from a bounded, allowlisted session directory."""
from __future__ import annotations

import json
from pathlib import Path
import re


def read_json(path: Path, default=None):
    try:
        if path.stat().st_size > 2_000_000:
            return default
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def session_root(root: Path, name: str = 'Latest') -> Path:
    sessions = (root / 'runs/sessions').resolve()
    if name == 'Latest':
        name = (read_json(root / 'runs/latest_session.json', {}) or {}).get('session', '')
        if not name:
            return root
    candidate = (sessions / name).resolve()
    if not name or candidate.parent != sessions or not candidate.is_dir():
        raise ValueError('Session directory is unavailable')
    return candidate


def artifact(root: Path, directory: str, module_id: str, suffix: str) -> str:
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', module_id):
        return 'Invalid module id'
    if (directory, suffix) not in {('legacy', '.cbl'), ('modern', '.py'), ('specs', '.json')}:
        raise ValueError('Unsupported artifact type')
    path = (root / directory / (module_id + suffix)).resolve()
    if not path.is_relative_to(root.resolve()):
        return 'Artifact is outside the session'
    try:
        if path.stat().st_size > 1_000_000:
            return 'Artifact is too large to display'
        return path.read_text()
    except OSError:
        return 'Waiting for this artifact…'


def calls(root: Path) -> list[dict]:
    path = root / 'runs/llm_calls.jsonl'
    if not path.exists() or path.stat().st_size > 2_000_000:
        return []
    result = []
    for line in path.read_text().splitlines()[-100:]:
        try:
            record = json.loads(line)
            result.append({key: record.get(key) for key in ('ts', 'model', 'model_id', 'source', 'seconds', 'ok', 'error')})
        except ValueError:
            continue
    return result
