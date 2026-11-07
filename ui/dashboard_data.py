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


def blocked_on(module: dict) -> str:
    """Dependency id a module is waiting on, or '' (run.py/graph error: 'blocked: dependency X not verified')."""
    match = re.match(r'blocked: dependency (\S+) not verified', module.get('error') or '')
    return match.group(1) if match else ''


def migration_chains(modules: dict) -> tuple[list[list[str]], list[str]]:
    """Split modules into dependency chains (callees first, e.g. [discount, invoice]) and standalone ids."""
    deps = {mid: [d for d in m.get('depends_on') or [] if d in modules] for mid, m in modules.items()}
    called = {d for ds in deps.values() for d in ds}
    chains = []
    for top in (mid for mid in modules if deps[mid] and mid not in called):
        order, seen = [], set()

        def visit(mid):
            if mid in seen:
                return
            seen.add(mid)
            for d in deps[mid]:
                visit(d)
            order.append(mid)
        visit(top)
        chains.append(order)
    standalone = [mid for mid in modules if not deps[mid] and mid not in called]
    return chains, standalone


def cobol_source(root: Path, module: dict, module_id: str) -> str:
    """Original COBOL from the module's cobol_path (any legacy dir), kept inside the session root."""
    path = module.get('cobol_path')
    if path:
        resolved = Path(path).resolve()
        if resolved.suffix == '.cbl' and resolved.is_relative_to(root.resolve()):
            try:
                return resolved.read_text() if resolved.stat().st_size <= 1_000_000 else 'Artifact is too large to display'
            except OSError:
                pass
    return artifact(root, 'legacy', module_id, '.cbl')


def copybooks(source: str) -> list[str]:
    """Copybook names a COBOL source COPYs, in order."""
    names = re.findall(r'^[^*]{0,6}\s*COPY\s+["\']?([A-Za-z0-9-]+)', source, flags=re.I | re.M)
    return list(dict.fromkeys(n.upper() for n in names))
