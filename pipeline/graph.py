"""
P1 (Hemant) — the assembly line. One graph run = one COBOL module.

  extract_spec -> record -> rewrite -> verify -+-> accept -> END
                               ^               |
                               +--- retry -----+   (failures fed back, max MAX_ATTEMPTS)
                                               |
                                               +-> explain -> END  (after MAX_ATTEMPTS, module failed)

`understand` runs once in run.py before the graph (it orders the modules).
"""
from __future__ import annotations

import os
import traceback
from pathlib import Path
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

import agents
import legacy
import testing
from pipeline import status

ROOT = Path(__file__).resolve().parents[1]
SPECS_DIR = ROOT / "specs"
MODERN_DIR = ROOT / "modern"
UNIT_DIR = ROOT / "tests" / "unit"
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))


class GraphState(TypedDict, total=False):
    id: str
    cobol_path: str
    cobol_src: str
    spec: Optional[dict]
    golden_path: Optional[str]
    py_path: Optional[str]
    python_src: Optional[str]
    status: str
    attempts: int
    tests_passed: int
    tests_total: int
    last_failures: list
    divergences: list
    error: Optional[str]


def _safe(node_name: str):
    """Wrap a node so one crash marks the module failed instead of killing the whole run."""
    def deco(fn):
        def wrapper(state: GraphState) -> GraphState:
            try:
                return fn(state)
            except Exception as e:
                err = f"{node_name}: {type(e).__name__}: {e}"
                traceback.print_exc()
                out = {**state, "status": "failed", "error": err}
                status.update(out, node_name, err)
                return out
        wrapper.__name__ = fn.__name__
        return wrapper
    return deco


# ---------- nodes ----------

@_safe("extract_spec")
def extract_spec(state: GraphState) -> GraphState:
    spec = agents.extract_spec(state["cobol_src"])
    spec["module_id"] = state["id"]  # keep ids consistent with file names
    SPECS_DIR.mkdir(exist_ok=True)
    (SPECS_DIR / f"{state['id']}.json").write_text(__import__("json").dumps(spec, indent=2))
    out = {**state, "spec": spec, "status": "spec"}
    status.update(out, "extract_spec", spec.get("summary", ""))
    return out


@_safe("record")
def record(state: GraphState) -> GraphState:
    inputs = agents.generate_inputs(state["spec"], state["cobol_src"])
    binary = legacy.compile_cobol(state["cobol_path"])
    golden = legacy.record_golden(state["id"], binary, inputs)
    out = {**state, "golden_path": golden, "status": "recorded", "tests_total": len(inputs)}
    status.update(out, "record", f"recorded {len(inputs)} golden cases")
    return out


@_safe("rewrite")
def rewrite(state: GraphState) -> GraphState:
    attempts = state.get("attempts", 0) + 1
    failures = state.get("last_failures") or None
    src = agents.rewrite(state["spec"], state["cobol_src"], failures)
    MODERN_DIR.mkdir(exist_ok=True)
    py_path = MODERN_DIR / f"{state['id']}.py"
    py_path.write_text(src)
    if attempts == 1:
        testing.golden_to_pytest(state["id"], str(py_path))
    out = {**state, "python_src": src, "py_path": str(py_path),
           "attempts": attempts, "status": "rewriting"}
    status.update(out, "rewrite", f"attempt {attempts}" + (" (fixing failures)" if failures else ""))
    return out


@_safe("verify")
def verify(state: GraphState) -> GraphState:
    res = testing.run_equivalence(state["id"])
    out = {**state, "tests_passed": res["passed"], "tests_total": res["total"],
           "last_failures": res["failures"], "status": "verifying"}
    status.update(out, "verify", f"{res['passed']}/{res['total']} equivalence tests passed")
    return out


@_safe("accept")
def accept(state: GraphState) -> GraphState:
    # unit tests are a bonus layer: failures here don't block acceptance
    try:
        UNIT_DIR.mkdir(parents=True, exist_ok=True)
        tests_src = agents.write_unit_tests(state["spec"], state["python_src"])
        (UNIT_DIR / f"test_{state['id']}_unit.py").write_text(tests_src)
        note = "unit tests written"
    except Exception as e:
        note = f"unit test writer failed: {e}"
    out = {**state, "status": "done", "last_failures": []}
    status.update(out, "accept", f"verified identical. {note}")
    return out


@_safe("explain")
def explain(state: GraphState) -> GraphState:
    divergences = []
    for f in state.get("last_failures", [])[:5]:  # cap LLM calls
        v = agents.explain_divergence(state["spec"], state["cobol_src"], state["python_src"], f)
        divergences.append({**v, **f})
    out = {**state, "divergences": divergences, "status": "failed"}
    quirks = sum(d["verdict"] == "legacy_quirk" for d in divergences)
    status.update(out, "explain", f"{len(divergences)} divergences explained ({quirks} legacy quirks)")
    return out


# ---------- routing ----------

def route_after_verify(state: GraphState) -> str:
    if state.get("status") == "failed":
        return "end"
    if not state.get("last_failures"):
        return "accept"
    if state.get("attempts", 0) < MAX_ATTEMPTS:
        return "retry"
    return "explain"


def stop_if_failed(next_node: str):
    def route(state: GraphState) -> str:
        return "end" if state.get("status") == "failed" else next_node
    return route


def build_graph():
    g = StateGraph(GraphState)
    for name, fn in [("extract_spec", extract_spec), ("record", record), ("rewrite", rewrite),
                     ("verify", verify), ("accept", accept), ("explain", explain)]:
        g.add_node(name, fn)
    g.set_entry_point("extract_spec")
    g.add_conditional_edges("extract_spec", stop_if_failed("record"), {"record": "record", "end": END})
    g.add_conditional_edges("record", stop_if_failed("rewrite"), {"rewrite": "rewrite", "end": END})
    g.add_conditional_edges("rewrite", stop_if_failed("verify"), {"verify": "verify", "end": END})
    g.add_conditional_edges("verify", route_after_verify,
                            {"accept": "accept", "retry": "rewrite", "explain": "explain", "end": END})
    g.add_edge("accept", END)
    g.add_edge("explain", END)
    return g.compile()
