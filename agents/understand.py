"""Phase 1 - Understand (no LLM).

    understand(legacy_dir) -> list[{module_id, cobol_path, depends_on: [module_id]}]   (leaves first)

Scans every COBOL program under legacy_dir, finds CALL and COPY dependencies with regex,
and returns the modules in dependency order (a module always comes after everything it
CALLs). Extra keys per module, safe to ignore: program_id, copybooks, unresolved_calls.

Also exports load_cobol_source(cobol_path): the source with COPY statements expanded,
which is what extract_spec should be given so it can see the copybook fields.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from agents.cobol_static import find_calls, find_copies, kw, program_id, strip_comments

PROGRAM_EXTS = {".cbl", ".cob", ".cobol"}
COPYBOOK_EXTS = {".cpy", ".copy", ".cbl", ".cob", ""}


def _module_id(path: Path) -> str:
    """File stem as a valid Python identifier, so modern/<id>.py is importable."""
    mid = re.sub(r"[^0-9a-zA-Z]+", "_", path.stem).strip("_").lower()
    return f"m_{mid}" if mid[:1].isdigit() else mid


def _is_program(path: Path, src: str) -> bool:
    return path.suffix.lower() in PROGRAM_EXTS and bool(
        re.search(kw("PROGRAM-ID"), strip_comments(src), re.I)
    )


def _copybook_index(root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in COPYBOOK_EXTS:
            index.setdefault(p.name.upper(), p)
            index.setdefault(p.stem.upper(), p)
    return index


def _resolve_copy(name: str, index: dict[str, Path]) -> Path | None:
    key = Path(name).name.upper()
    return index.get(key) or index.get(Path(key).stem)


def load_cobol_source(cobol_path, search_dir=None, _depth: int = 0) -> str:
    """Return the program source with every resolvable `COPY name.` replaced by the copybook text."""
    path = Path(cobol_path)
    src = path.read_text(errors="replace")
    if _depth > 5:
        return src
    index = _copybook_index(Path(search_dir) if search_dir else path.parent)

    def repl(m: re.Match) -> str:
        cp = _resolve_copy(m.group(2) or m.group(3), index)
        if not cp or cp.resolve() == path.resolve():
            return m.group(0)
        body = load_cobol_source(cp, search_dir or path.parent, _depth + 1)
        return f"      *> ---- COPY {cp.name} ----\n{body}\n      *> ---- end {cp.name} ----"

    pattern = r"^[^\n*]*?" + kw("COPY") + r"\s+(?:(['\"])([^'\"\n]+)\1|([A-Za-z0-9][A-Za-z0-9_.-]*?))\s*\.?[ \t]*$"
    return re.sub(pattern, repl, src, flags=re.I | re.M)


def _toposort(mods: dict[str, dict]) -> list[str]:
    deps = {m: set(info["depends_on"]) for m, info in mods.items()}
    order: list[str] = []
    ready = sorted(m for m, d in deps.items() if not d)
    while ready:
        m = ready.pop(0)
        order.append(m)
        for other in sorted(deps):
            if m in deps[other]:
                deps[other].discard(m)
                if not deps[other] and other not in order and other not in ready:
                    ready.append(other)
        ready.sort()
    leftover = sorted(m for m in mods if m not in order)
    if leftover:
        print(f"[understand] WARNING: dependency cycle among {leftover}; appending in name order", file=sys.stderr)
        order.extend(leftover)
    return order


def understand(legacy_dir) -> list[dict]:
    root = Path(legacy_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"legacy_dir not found: {root}")
    copy_index = _copybook_index(root)

    mods: dict[str, dict] = {}
    by_name: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in PROGRAM_EXTS:
            continue
        src = path.read_text(errors="replace")
        if not _is_program(path, src):
            continue  # a copybook that happens to use a .cbl extension
        mid = _module_id(path)
        if mid in mods:
            print(f"[understand] WARNING: duplicate module id {mid} ({path}); skipped", file=sys.stderr)
            continue
        pid = program_id(src) or path.stem.upper()
        calls, dynamic = find_calls(src)
        mods[mid] = {"module_id": mid, "cobol_path": str(path), "program_id": pid,
                     "_calls": calls, "_copies": find_copies(src), "_dynamic": dynamic}
        by_name[pid.upper()] = mid
        by_name.setdefault(path.stem.upper(), mid)

    for mid, info in mods.items():
        depends, unresolved, copybooks = [], [], []
        for target in info.pop("_calls"):
            dep = by_name.get(target.upper())
            if dep and dep != mid:
                depends.append(dep)
            elif not dep:
                unresolved.append(target)
        for name in info.pop("_copies"):
            dep = by_name.get(Path(name).stem.upper())
            cp = _resolve_copy(name, copy_index)
            if dep and dep != mid and cp and _is_program(cp, cp.read_text(errors="replace")):
                depends.append(dep)  # COPY of another program file
            elif cp:
                copybooks.append(str(cp))
            else:
                unresolved.append(f"COPY {name}")
        dynamic = info.pop("_dynamic")
        unresolved += [f"{d} (dynamic CALL)" for d in dynamic]
        if unresolved:
            print(f"[understand] {mid}: unresolved {unresolved}", file=sys.stderr)
        info.update(depends_on=sorted(set(depends)), copybooks=copybooks, unresolved_calls=unresolved)

    return [mods[m] for m in _toposort(mods)]
