"""The local demo server: lists codebases, accepts only COBOL from a zip, refuses bad input."""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import serve  # noqa: E402


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(serve, "UPLOADS", tmp_path / "samples" / "uploads")
    monkeypatch.setattr(serve, "ROOT", tmp_path)
    return tmp_path


def test_codebases_lists_the_samples_with_titles():
    names = {c["codebase"]: c for c in serve._codebases()}
    assert names["samples/bank"]["programs"] == 5 and names["samples/bank"]["name"] == "Retail bank"
    assert names["samples/legacy"]["programs"] == 3


def test_upload_keeps_only_cobol_and_blocks_path_tricks(uploads):
    code, body = serve._safe_upload(_zip({
        "bank/acct.cbl": b"       PROGRAM-ID. ACCT.\n",
        "bank/copybooks/REC.cpy": b"01 REC PIC X.\n",
        "../../escape.cbl": b"       PROGRAM-ID. EVIL.\n",
        "bank/run.sh": b"rm -rf /\n",
        "__MACOSX/bank/._acct.cbl": b"junk",
    }), "My Bank.zip")
    assert code == 200 and body["files"] == 2
    dest = uploads / body["codebase"]
    assert sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()) == ["bank/acct.cbl", "bank/copybooks/REC.cpy"]
    assert not (uploads.parent / "escape.cbl").exists() and not (uploads / "escape.cbl").exists()


def test_upload_refuses_non_zip_and_empty(uploads):
    assert serve._safe_upload(b"not a zip", "x.zip")[0] == 400
    assert serve._safe_upload(_zip({"readme.txt": b"hi"}), "x.zip")[0] == 400


def test_start_refuses_unknown_codebase():
    assert serve._start("../../etc")[0] == 400


def test_replay_refuses_bad_session_names():
    assert serve._replay("../../etc/passwd")[0] == 400
    assert serve._replay("20991231-000000-real-abcdef")[0] == 202  # not started yet


def test_dropping_the_demo_zip_is_recognised_as_the_bank(uploads):
    code, body = serve._safe_upload((ROOT / "demo" / "retail-bank.zip").read_bytes(), "retail-bank.zip")
    assert code == 200 and body["files"] == 6
    about = serve._about(uploads / body["codebase"])
    assert about["same_as"] == "samples/bank" and about["title"] == "Retail bank"
    assert serve._recording_for(body["codebase"]) == "bank"  # so "Switch to recording" works after a live drop


def test_a_different_zip_is_its_own_codebase(uploads):
    code, body = serve._safe_upload(_zip({"x/a.cbl": b"       PROGRAM-ID. A.\n"}), "x.zip")
    assert code == 200 and "same_as" not in serve._about(uploads / body["codebase"])
