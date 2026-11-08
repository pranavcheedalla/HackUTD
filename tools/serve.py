"""Local server for the galaxy page: pick or drop a COBOL codebase and watch it migrate live.

    python tools/serve.py            # then open http://127.0.0.1:8765
    python tools/serve.py --port 9000

It serves web/ and a small JSON API:

    GET  /api/status                      live runs possible? (API key present) and the run in progress
    GET  /api/codebases                   COBOL folders under samples/ and which have a recorded replay
    POST /api/upload                      body: a .zip of COBOL; saved to samples/uploads/<name>/
    POST /api/runs        {"codebase"}    start a real run (tools/isolated_run.py); returns the session
    GET  /api/runs/<session>/replay       that session as a replay, built from what it has written so far

A run is the same pipeline as the command line, in its own session copy. Only one runs at a time
(isolated_run.py holds the lock). The page falls back to the recorded replay whenever live isn't
available. Bind stays on 127.0.0.1: this is a local demo tool, not a public service.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import zipfile
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import export_replay  # noqa: E402

WEB = ROOT / "web"
SAMPLES = ROOT / "samples"
UPLOADS = SAMPLES / "uploads"
SESSIONS = ROOT / "runs" / "sessions"
SOURCE_EXT = {".cbl", ".cob", ".cobol", ".cpy", ".copy"}
MAX_UPLOAD = 5 * 1024 * 1024
MAX_FILES = 200
SESSION_RE = re.compile(r"^[0-9]{8}-[0-9]{6}-(real|fake)-[0-9a-f]{6}$")

_lock = threading.Lock()
_current: dict = {}  # {"session", "codebase", "process", "started"}


def _api_key() -> bool:
    try:
        from dotenv import dotenv_values
        key = (dotenv_values(ROOT / ".env") or {}).get("NVIDIA_API_KEY") or os.getenv("NVIDIA_API_KEY", "")
    except ImportError:
        key = os.getenv("NVIDIA_API_KEY", "")
    return key.startswith("nvapi-")


def _recordings() -> dict:
    """codebase folder (relative) → replay name, from web/replays/index.json."""
    try:
        index = json.loads((WEB / "replays" / "index.json").read_text())
    except (OSError, ValueError):
        return {}
    return {r["codebase"]: r["name"] for r in index if r.get("codebase")}


def _codebases() -> list[dict]:
    recs = _recordings()
    out = []
    folders = sorted(p for p in SAMPLES.iterdir() if p.is_dir() and p.name != "uploads")
    if UPLOADS.is_dir():
        folders += sorted(p for p in UPLOADS.iterdir() if p.is_dir())
    for folder in folders:
        files = [f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in SOURCE_EXT]
        programs = [f for f in files if f.suffix.lower() in {".cbl", ".cob", ".cobol"}
                    and re.search(r"PROGRAM-ID", f.read_text(errors="replace"), re.I)]
        if not programs:
            continue
        rel = folder.relative_to(ROOT).as_posix()
        about = {}
        try:  # optional samples/<name>/codebase.json: {"title", "about"}
            about = json.loads((folder / "codebase.json").read_text())
        except (OSError, ValueError):
            pass
        out.append({"codebase": rel, "name": str(about.get("title") or folder.name)[:60], "about": str(about.get("about") or "")[:200],
                    "programs": len(programs),
                    "copybooks": len(files) - len(programs), "uploaded": folder.parent == UPLOADS,
                    "recording": recs.get(rel)})
    return out


def _running() -> str | None:
    p = _current.get("process")
    return _current.get("session") if p and p.poll() is None else None


def _start(codebase: str) -> tuple[int, dict]:
    known = {c["codebase"] for c in _codebases()}
    if codebase not in known:
        return 400, {"error": "Unknown codebase."}
    if not _api_key():
        return 409, {"error": "Live runs need NVIDIA_API_KEY in .env. Watching the recording instead."}
    with _lock:
        if _running():
            return 409, {"error": "A run is already in progress.", "session": _current["session"]}
        latest = ROOT / "runs" / "latest_session.json"
        before = latest.read_text() if latest.exists() else ""
        log = (ROOT / "runs" / "live-runs.log").open("a")
        proc = subprocess.Popen([sys.executable, str(ROOT / "tools" / "isolated_run.py"), "--mode", "real",
                                 "--legacy-dir", codebase], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        session = None
        for _ in range(60):  # isolated_run publishes its session name right after copying the repo
            time.sleep(.25)
            if proc.poll() is not None:
                break
            if latest.exists() and latest.read_text() != before:
                session = json.loads(latest.read_text()).get("session"); break
        if not session:
            if proc.poll() is None:
                proc.terminate()
            tail = (ROOT / "runs" / "live-runs.log").read_text(errors="replace")[-600:]
            if "already active" in tail:  # isolated_run's lock: a run started elsewhere is still going
                return 409, {"error": "Another run is in progress. Watch it, or try again when it finishes."}
            return 500, {"error": "The run could not start. See runs/live-runs.log."}
        _current.update(session=session, codebase=codebase, process=proc, started=time.time())
        return 200, {"session": session, "codebase": codebase}


def _safe_upload(data: bytes, name: str) -> tuple[int, dict]:
    if len(data) > MAX_UPLOAD:
        return 413, {"error": "That file is over 5 MB."}
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return 400, {"error": "Drop a .zip of COBOL files."}
    slug = re.sub(r"[^a-z0-9]+", "-", Path(name or "upload").stem.lower()).strip("-")[:30] or "upload"
    dest = UPLOADS / f"{slug}-{time.strftime('%H%M%S')}"
    kept = 0
    for info in zf.infolist():
        if info.is_dir() or kept >= MAX_FILES:
            continue
        parts = [p for p in Path(info.filename).parts if p not in ("", ".")]
        if not parts or any(p == ".." or p.startswith("/") or p.startswith("__MACOSX") or p.startswith(".") for p in parts):
            continue
        if Path(parts[-1]).suffix.lower() not in SOURCE_EXT or info.file_size > 1024 * 1024:
            continue
        target = dest.joinpath(*parts).resolve()
        if not target.is_relative_to(dest.resolve()):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zf.read(info))
        kept += 1
    if not kept:
        return 400, {"error": "No COBOL files (.cbl, .cob, .cpy) found in that zip."}
    return 200, {"codebase": dest.relative_to(ROOT).as_posix(), "files": kept}


def _replay(session: str) -> tuple[int, dict]:
    if not SESSION_RE.match(session):
        return 400, {"error": "Bad session."}
    folder = SESSIONS / session
    if not (folder / "runs" / "state.json").is_file():
        return 202, {"pending": True}  # copied, pipeline not started yet
    try:
        rep = export_replay.export_session(folder)
    except (OSError, ValueError, KeyError) as exc:
        return 202, {"pending": True, "detail": type(exc).__name__}
    meta = {}
    try:
        meta = json.loads((folder / "session.json").read_text())
    except (OSError, ValueError):
        pass
    rep.update(name=session, title=Path(meta.get("legacy_dir") or session).name, live=True,
               finished=meta.get("status") in ("done", "failed"), codebase=meta.get("legacy_dir"),
               recording=_recordings().get(meta.get("legacy_dir") or ""))
    return 200, rep


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(WEB), **k)

    def log_message(self, fmt, *args):  # quiet: only API calls
        if self.path.startswith("/api/") and not self.path.endswith("/replay"):
            sys.stderr.write("[serve] " + fmt % args + "\n")

    def _json(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/status":
            return self._json(200, {"live": _api_key(), "running": _running()})
        if self.path == "/api/codebases":
            return self._json(200, {"codebases": _codebases()})
        m = re.match(r"^/api/runs/([^/]+)/replay$", self.path)
        if m:
            return self._json(*_replay(m.group(1)))
        if self.path.startswith("/api/"):
            return self._json(404, {"error": "Not found."})
        return super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD + 1024:
            return self._json(413, {"error": "That file is over 5 MB."})
        body = self.rfile.read(length) if length else b""
        if self.path == "/api/upload":
            return self._json(*_safe_upload(body, self.headers.get("X-Filename", "upload.zip")))
        if self.path == "/api/runs":
            try:
                codebase = json.loads(body or b"{}").get("codebase", "")
            except ValueError:
                return self._json(400, {"error": "Bad request."})
            return self._json(*_start(codebase))
        return self._json(404, {"error": "Not found."})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Legacy → Verified: http://127.0.0.1:{args.port}  (live runs {'on' if _api_key() else 'off: no NVIDIA_API_KEY'})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
