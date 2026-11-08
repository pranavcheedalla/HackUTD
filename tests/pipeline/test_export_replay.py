"""The galaxy page replays exported runs: no absolute paths, real history, safe fallbacks."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("export_replay", ROOT / "tools" / "export_replay.py")
export_replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_replay)


def _session(tmp_path, history=True):
    s = tmp_path / "20261107-000000-real-abc123"
    (s / "runs").mkdir(parents=True)
    (s / "samples" / "legacy").mkdir(parents=True)
    (s / "samples" / "legacy" / "invoice.cbl").write_text("       PROGRAM-ID. INVOICE.\n")
    (s / "modern").mkdir()
    (s / "modern" / "invoice.py").write_text("KEY = 'nvapi-abcdef123'\ndef main(s):\n    return s\n")
    (s / "golden").mkdir()
    (s / "golden" / "invoice.jsonl").write_text('{"input": "1|2|3", "output": "TOTAL=1"}\n')
    module = {"id": "invoice", "cobol_path": f"/Users/someone/x/{s.name}/samples/legacy/invoice.cbl",
              "status": "done", "attempts": 2, "tests_passed": 30, "tests_total": 30, "depends_on": ["discount"]}
    if history:
        module["history"] = [{"attempt": 1, "passed": 26, "total": 30, "explanation": None,
                              "failures": [{"input": "1|12.35|0.01", "expected": "12.34", "actual": "12.35"}]}]
    events = [{"t": "x", "module": "invoice", "node": "verify", "msg": "26/30 equivalence tests passed"},
              {"t": "y", "module": "invoice", "node": "verify", "msg": "30/30 equivalence tests passed"}]
    (s / "runs" / "state.json").write_text(json.dumps({"mode": "real_model", "started_at": "2026-11-07T00:00:00",
                                                       "modules": {"invoice": module}, "events": events}))
    return s


def test_export_keeps_real_data_and_drops_paths_and_keys(tmp_path):
    rep = export_replay.export_session(_session(tmp_path))
    text = json.dumps(rep)
    assert "/Users/" not in text and "nvapi-abcdef123" not in text
    (m,) = rep["modules"]
    assert m["file"] == "invoice.cbl" and "PROGRAM-ID. INVOICE." in m["cobol"]
    assert m["history"][0]["failures"][0]["actual"] == "12.35"
    assert m["golden"] == [{"input": "1|2|3", "output": "TOTAL=1"}]


def test_older_runs_get_count_only_history_from_events(tmp_path):
    rep = export_replay.export_session(_session(tmp_path, history=False))
    hist = rep["modules"][0]["history"]
    assert [(h["passed"], h["total"]) for h in hist] == [(26, 30), (30, 30)]
    assert all(h["failures"] == [] for h in hist)


def test_committed_demo_replays_are_clean():
    for path in (ROOT / "web" / "replays").glob("*.json"):
        text = path.read_text()
        assert "/Users/" not in text and "/private/" not in text, path
        assert not __import__("re").search(r"nvapi-[A-Za-z0-9]{6}", text), path
