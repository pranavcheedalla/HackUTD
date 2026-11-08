"""Turn a finished run into a self-contained replay for the galaxy page (web/).

    python tools/export_replay.py runs/sessions/<session> --name codebase --title "Multi-file codebase"
    python tools/export_replay.py runs/sessions/<session>-mutation --mutation --name planted-bug

The replay holds only what the run recorded (state.json events and per-attempt history,
specs, the COBOL source, the verified Python, the golden answer key) with no absolute
paths or secrets, so the page can play it back offline, identically, on any laptop.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "web" / "replays"
MAX_GOLDEN = 40
SECRET = re.compile(r"nvapi-[A-Za-z0-9_-]+")


def _read(path: Path) -> str:
    try:
        return SECRET.sub("nvapi-…", path.read_text(errors="replace"))
    except OSError:
        return ""


def _cobol(session: Path, module: dict) -> tuple[str, str]:
    """(file name, source) of the module's COBOL, found inside the session copy."""
    raw = module.get("cobol_path") or ""
    name = Path(raw).name or f"{module['id']}.cbl"
    marker = f"/{session.name}/"
    if marker in raw:
        candidate = session / raw.split(marker, 1)[1]
        if candidate.is_file():
            return name, _read(candidate)
    for hit in session.rglob(name):
        if "sessions" not in hit.relative_to(session).parts:
            return name, _read(hit)
    return name, ""


def _golden(session: Path, mid: str) -> list[dict]:
    rows = []
    for line in _read(session / "golden" / f"{mid}.jsonl").splitlines()[:MAX_GOLDEN]:
        try:
            case = json.loads(line)
            rows.append({"input": case["input"], "output": case["output"]})
        except (ValueError, KeyError):
            continue
    return rows


def _history_from_events(events: list[dict], mid: str) -> list[dict]:
    """Older runs kept only counts in their verify events; rebuild a count-only history."""
    out = []
    for e in events:
        m = re.match(r"(\d+)/(\d+) equivalence", e.get("msg", ""))
        if e.get("module") == mid and e.get("node") == "verify" and m:
            passed, total = int(m.group(1)), int(m.group(2))
            out.append({"attempt": len(out) + 1, "passed": passed, "total": total,
                        "failures": [], "explanation": None})
    return out


def export_session(session: Path) -> dict:
    state = json.loads((session / "runs" / "state.json").read_text())
    events = [{k: e.get(k) for k in ("t", "module", "node", "msg")} for e in state.get("events", [])]
    modules = []
    for mid, m in state["modules"].items():
        file_name, cobol = _cobol(session, m)
        history = m.get("history") or _history_from_events(events, mid)
        modules.append({
            "id": mid, "file": file_name, "program_id": m.get("program_id") or mid.upper(),
            "kind": m.get("kind", "program"), "depends_on": m.get("depends_on", []),
            "status": m.get("status", "pending"), "error": m.get("error"),
            "attempts": m.get("attempts", 0), "tests_passed": m.get("tests_passed", 0),
            "tests_total": m.get("tests_total", 0), "history": history,
            "divergences": [{k: d.get(k) for k in ("input", "expected", "actual", "verdict", "reason")}
                            for d in m.get("divergences") or []],
            "unit_tests_status": m.get("unit_tests_status"),
            "unit_tests_quarantined": m.get("unit_tests_quarantined", []),
            "spec": m.get("spec"), "cobol": cobol, "python": _read(session / "modern" / f"{mid}.py"),
            "golden": _golden(session, mid),
        })
    return {"kind": "run", "mode": state.get("mode", "real_model"), "session": session.name,
            "started_at": state.get("started_at"), "modules": modules, "events": events}


def export_mutation(session: Path) -> dict:
    """The controlled mutation check as a one-module replay: planted bug, caught, repaired."""
    report = json.loads((session / "runs" / "mutation_check.json").read_text())
    replay = export_session(session)
    target = next((m for m in replay["modules"] if m["id"] == "invoice"), replay["modules"][0])
    cases = report["cases"]
    mutant = report["mutant"]
    explanation = report.get("explanation") or {}
    failure = explanation.get("failure") or (mutant["failures"] or [{}])[0]
    history = [{"attempt": 1, "passed": cases - mutant["failed"], "total": cases,
                "failures": mutant["failures"][:5],
                "explanation": {"verdict": explanation.get("verdict"), "reason": explanation.get("reason"),
                                "input": failure.get("input")}}]
    for repair in report.get("repairs", []):
        history.append({"attempt": len(history) + 1, "passed": cases - repair["failed"], "total": cases,
                        "failures": [], "explanation": None})
    target.update(history=history, attempts=len(history), status="done" if report.get("result") == "repaired" else "failed",
                  tests_passed=history[-1]["passed"], tests_total=cases, depends_on=[])
    return {"kind": "mutation", "mode": "controlled_mutation", "label": report.get("label"),
            "session": session.name, "started_at": replay["started_at"], "modules": [target], "events": []}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", type=Path)
    ap.add_argument("--name", required=True, help="replay file name, e.g. codebase")
    ap.add_argument("--title", default="", help="shown in the page's session menu")
    ap.add_argument("--mutation", action="store_true", help="export the planted-bug mutation check")
    args = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,40}", args.name):
        ap.error("--name: lowercase letters, digits and dashes only")
    if not (args.session / "runs" / "state.json").is_file():
        ap.error(f"not a finished session folder: {args.session}")
    replay = export_mutation(args.session) if args.mutation else export_session(args.session)
    replay.update(name=args.name, title=args.title or args.name)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{args.name}.json").write_text(json.dumps(replay, indent=1))
    index_path = OUT_DIR / "index.json"
    index = json.loads(index_path.read_text()) if index_path.is_file() else []
    index = [r for r in index if r["name"] != args.name] + [{"name": args.name, "title": replay["title"],
                                                             "kind": replay["kind"]}]
    index_path.write_text(json.dumps(index, indent=1))
    done = sum(m["status"] == "done" for m in replay["modules"])
    print(f"web/replays/{args.name}.json: {len(replay['modules'])} modules, {done} verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
