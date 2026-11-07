"""P1 (Hemant): graph/run.py wire codebase support; isolated_run takes any legacy dir.

State keys run.py adds to each module's initial graph state (from agents.understand):
  kind, program_id, link, copy_dirs, params, depends_on,
  dep_modules: [{"module_id", "program_id", "params", "status"}]  for each depends_on,
               status = that module's final status earlier in this run.
"""
import subprocess
import sys

import pytest

from cbhelpers import FIXTURES, ROOT, SAMPLES, pending

OWNER = "P1 Hemant, pipeline/graph.py + run.py + tools/isolated_run.py + ui/"
graph = pytest.importorskip("pipeline.graph")


@pytest.fixture
def quiet(monkeypatch, tmp_path):
    if not hasattr(graph, "DRIVERS_DIR"):
        pending(OWNER, "pipeline.graph.DRIVERS_DIR (where generated drivers are written: runs/drivers)")
    monkeypatch.setattr(graph.status, "update", lambda *a, **k: None)
    monkeypatch.setattr(graph, "DRIVERS_DIR", tmp_path / "drivers")
    monkeypatch.setattr(graph, "MODERN_DIR", tmp_path / "modern")
    monkeypatch.setattr(graph.testing, "golden_to_pytest", lambda *a, **k: "")
    return tmp_path


def _state(module_id, **extra):
    base = {"id": module_id, "cobol_path": str(SAMPLES / f"{module_id}.cbl"),
            "cobol_src": (SAMPLES / f"{module_id}.cbl").read_text(), "spec": {"module_id": module_id},
            "attempts": 0, "divergences": [], "last_failures": [], "kind": "program", "link": [],
            "copy_dirs": [], "params": [], "depends_on": [], "dep_modules": []}
    return {**base, **extra}


def test_record_compiles_subprogram_through_generated_driver(quiet, monkeypatch):
    seen = {}
    monkeypatch.setattr(graph.agents, "generate_inputs", lambda spec, src: ["G|1.00|0"])
    monkeypatch.setattr(graph.agents, "make_driver", lambda src: "DRIVER SOURCE")
    monkeypatch.setattr(graph.legacy, "compile_program",
                        lambda path, link=(), copy_dirs=(), **k: seen.update(path=path, link=list(link)) or "bin")
    monkeypatch.setattr(graph.legacy, "record_golden", lambda mid, binary, inputs: f"golden/{mid}.jsonl")
    out = graph.record(_state("discount", kind="subprogram"))
    assert out["status"] == "recorded", out.get("error")
    assert open(seen["path"]).read() == "DRIVER SOURCE"
    assert seen["link"][0] == str(SAMPLES / "discount.cbl")


def test_record_compiles_program_with_links_and_copybooks(quiet, monkeypatch):
    seen = {}
    monkeypatch.setattr(graph.agents, "generate_inputs", lambda spec, src: ["00020050000G"])
    monkeypatch.setattr(graph.legacy, "compile_program",
                        lambda path, link=(), copy_dirs=(), **k: seen.update(path=path, link=list(link),
                                                                             copy_dirs=list(copy_dirs)) or "bin")
    monkeypatch.setattr(graph.legacy, "record_golden", lambda mid, binary, inputs: f"golden/{mid}.jsonl")
    link, dirs = [str(SAMPLES / "discount.cbl")], [str(SAMPLES / "copybooks")]
    out = graph.record(_state("invoice", link=link, copy_dirs=dirs))
    assert out["status"] == "recorded", out.get("error")
    assert seen == {"path": str(SAMPLES / "invoice.cbl"), "link": link, "copy_dirs": dirs}


def test_rewrite_passes_verified_dependencies(quiet, monkeypatch):
    (quiet / "modern").mkdir()
    (quiet / "modern" / "discount.py").write_text((FIXTURES / "modern" / "discount.py").read_text())
    seen = {}
    monkeypatch.setattr(graph.agents, "rewrite", lambda spec, src, failures=None, **k: seen.update(k) or "def main(l): return l")
    dep = {"module_id": "discount", "program_id": "DISCOUNT", "params": [], "status": "done"}
    out = graph.rewrite(_state("invoice", depends_on=["discount"], dep_modules=[dep]))
    assert out["status"] == "rewriting", out.get("error")
    (info,) = seen["deps"]
    assert info["module_id"] == "discount" and info["program_id"] == "DISCOUNT"
    assert "def call(" in info["python_src"]


def test_unverified_dependency_blocks_the_caller(quiet, monkeypatch):
    monkeypatch.setattr(graph.agents, "rewrite", lambda *a, **k: pytest.fail("must not call the model"))
    dep = {"module_id": "discount", "program_id": "DISCOUNT", "params": [], "status": "failed"}
    out = graph.rewrite(_state("invoice", depends_on=["discount"], dep_modules=[dep]))
    assert out["status"] == "failed"
    assert out["error"].startswith("blocked: dependency discount not verified")


def test_isolated_run_accepts_any_legacy_dir():
    help_text = subprocess.run([sys.executable, str(ROOT / "tools" / "isolated_run.py"), "--help"],
                               capture_output=True, text=True).stdout
    if "--legacy-dir" not in help_text:
        pending(OWNER, "tools/isolated_run.py --legacy-dir")
    assert "{interest,payroll,invoice}" not in help_text, "--only must accept any module id"
