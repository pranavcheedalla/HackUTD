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

import json
import os
import time
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
DRIVERS_DIR = ROOT / "runs" / "drivers"  # generated test drivers for subprograms
FEEDBACK_DIR = ROOT / "runs" / "feedback"  # human hints, one <module>.json each (tools/serve.py writes them)
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))
MIN_TESTS = int(os.getenv("MIN_TESTS", "5"))  # never call a module verified on fewer distinct cases
MAX_RECORDED_FAILURES = 5  # failed cases kept per attempt in runs/state.json
HINT_WAIT = float(os.getenv("HINT_WAIT", "0"))  # seconds a retry waits for a human hint (0: never waits)
MAX_HINT_CHARS = 500


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
    unit_tests_status: str
    unit_tests_quarantined: list
    # codebase support: LangGraph drops undeclared keys, so every key run.py passes must be here
    kind: str                # "program" | "subprogram"
    program_id: str
    link: list               # absolute callee .cbl paths, callees first
    copy_dirs: list          # absolute copybook dirs
    params: list             # LINKAGE params (subprograms only)
    depends_on: list
    dep_modules: list        # [{module_id, program_id, params, status}] per dependency
    history: list            # one attempt_record per verify: counts, failed cases, explanation
    attempt_sources: list    # [{attempt, python}] each rewrite's source, kept for the replay
    human_hints: list        # [{attempt, note, at}] reviewer hints, and the attempt that first used each


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


def _compile(path: str, link: list, copy_dirs: list) -> str:
    try:
        return legacy.compile_program(path, link=link, copy_dirs=copy_dirs)
    except NotImplementedError:
        # P2's compile_program not merged yet: single-file programs still compile the old way
        if link or copy_dirs:
            raise
        return legacy.compile_cobol(path)


def clean_inputs(raw) -> tuple[list[str], int]:
    """Keep each usable test input once: one line of text, in the agent's order.
    Returns (inputs, how many were dropped). One bad line no longer sinks the module."""
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f"generate_inputs must return a list of strings, got {type(raw).__name__}")
    seen, out = set(), []
    for item in raw:
        if not isinstance(item, str) or "\n" in item or "\r" in item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out, len(raw) - len(out)


@_safe("record")
def record(state: GraphState) -> GraphState:
    inputs, dropped = clean_inputs(agents.generate_inputs(state["spec"], state["cobol_src"]))
    if dropped:
        print(f"[record] {state['id']}: dropped {dropped} duplicate or unusable test input(s)")
    link, copy_dirs = list(state.get("link") or []), list(state.get("copy_dirs") or [])
    if state.get("kind") == "subprogram":
        # a subprogram has no input of its own; a generated driver CALLs it (inputs are driver-format)
        DRIVERS_DIR.mkdir(parents=True, exist_ok=True)
        driver = DRIVERS_DIR / f"{state['id']}_driver.cbl"
        driver.write_text(agents.make_driver(state["cobol_src"]))
        binary = _compile(str(driver), [state["cobol_path"], *link], copy_dirs)
    else:
        binary = _compile(state["cobol_path"], link, copy_dirs)
    golden = legacy.record_golden(state["id"], binary, inputs)
    out = {**state, "golden_path": golden, "status": "recorded", "tests_total": len(inputs)}
    status.update(out, "record", f"recorded {len(inputs)} golden cases")
    return out


def read_hints(module_id: str) -> list[dict]:
    """Reviewer hints for a module: [{note, at}], oldest first. A missing or broken file is no hints."""
    try:
        raw = json.loads((FEEDBACK_DIR / f"{module_id}.json").read_text())
    except (OSError, ValueError):
        return []
    return [{"note": str(h["note"])[:MAX_HINT_CHARS], "at": h.get("at")}
            for h in raw if isinstance(h, dict) and str(h.get("note") or "").strip()] if isinstance(raw, list) else []


def wait_for_hint(state: GraphState, seen: int) -> list[dict]:
    """Before a retry, give a reviewer up to HINT_WAIT seconds to add a hint. Returns all hints."""
    hints = read_hints(state["id"])
    if HINT_WAIT <= 0 or len(hints) > seen:
        return hints
    status.update(state, "hint_window", f"waiting up to {HINT_WAIT:g}s for a reviewer hint")
    deadline = time.monotonic() + HINT_WAIT
    while time.monotonic() < deadline:
        time.sleep(0.5)
        hints = read_hints(state["id"])
        if len(hints) > seen:
            break
    return hints


def with_hints(spec: dict, hints: list[dict]) -> dict:
    """The spec the rewrite agent sees: reviewer hints added as business rules it must follow.
    Hints only guide the rewrite; acceptance still needs every golden case to match."""
    if not hints:
        return spec
    rules = list(spec.get("business_rules") or [])
    return {**spec, "business_rules": rules + [f"Reviewer hint (must follow): {h['note']}" for h in hints]}


@_safe("rewrite")
def rewrite(state: GraphState) -> GraphState:
    dep_modules = state.get("dep_modules") or []
    for dep in dep_modules:
        if dep.get("status") != "done":
            # returned, not raised: _safe would prefix the error with "rewrite: ..."
            out = {**state, "status": "failed",
                   "error": f"blocked: dependency {dep['module_id']} not verified"}
            status.update(out, "rewrite", out["error"])
            return out
    deps = [{"module_id": d["module_id"], "program_id": d.get("program_id", ""),
             "params": d.get("params", []),
             "python_src": (MODERN_DIR / f"{d['module_id']}.py").read_text()}
            for d in dep_modules]
    attempts = state.get("attempts", 0) + 1
    failures = state.get("last_failures") or None
    used = list(state.get("human_hints") or [])
    hints = wait_for_hint(state, len(used)) if failures else read_hints(state["id"])
    new = [{"attempt": attempts, **h} for h in hints[len(used):]]
    spec = with_hints(state["spec"], hints)
    if deps:
        src = agents.rewrite(spec, state["cobol_src"], failures, deps=deps)
    else:
        src = agents.rewrite(spec, state["cobol_src"], failures)
    MODERN_DIR.mkdir(exist_ok=True)
    py_path = MODERN_DIR / f"{state['id']}.py"
    py_path.write_text(src)
    if attempts == 1:
        testing.golden_to_pytest(state["id"], str(py_path))
    out = {**state, "python_src": src, "py_path": str(py_path),
           "attempts": attempts, "status": "rewriting",
           "attempt_sources": [*(state.get("attempt_sources") or []),
                               {"attempt": attempts, "python": src[:20000]}],
           "human_hints": used + new}
    status.update(out, "rewrite", f"attempt {attempts}" + (" (fixing failures)" if failures else "")
                  + (f" (using {len(new)} human hint{'s' * (len(new) > 1)})" if new else ""))
    return out


@_safe("verify")
def verify(state: GraphState) -> GraphState:
    # a rewrite must compute its answer: one that reads files (e.g. the golden answer key)
    # or imports anything but pure stdlib + verified dependencies is never accepted
    local = [d["module_id"] for d in state.get("dep_modules") or []]
    problems = testing.rewrite_violations(state.get("python_src") or "", local)
    if problems:
        out = {**state, "status": "failed", "tests_passed": 0,
               "error": "rejected: rewrite is not self-contained: " + "; ".join(problems[:3])}
        status.update(out, "verify", out["error"])
        return out
    res = testing.run_equivalence(state["id"])
    if res["total"] < MIN_TESTS:
        out = {**state, "status": "failed", "tests_passed": res["passed"], "tests_total": res["total"],
               "error": f"too few distinct test cases to verify ({res['total']} < {MIN_TESTS})"}
        status.update(out, "verify", out["error"])
        return out
    record = attempt_record(state, res)
    failures = [dict(f) for f in res["failures"]]
    ex = record.get("explanation") or {}
    if failures and ex.get("verdict"):  # the retry sees why, not only what, it got wrong
        failures[0]["why"] = ex.get("reason")
    out = {**state, "tests_passed": res["passed"], "tests_total": res["total"],
           "last_failures": failures, "status": "verifying",
           "history": [*(state.get("history") or []), record]}
    status.update(out, "verify", f"{res['passed']}/{res['total']} equivalence tests passed")
    return out


def attempt_record(state: GraphState, res: dict) -> dict:
    """What one verify saw, kept after the module passes so a replay can show the real mismatch.
    A failure that will be retried also gets one explanation (after the last attempt the
    explain node explains up to five instead). An explainer error never fails the module."""
    attempt = state.get("attempts", 0)
    record = {"attempt": attempt, "passed": res["passed"], "total": res["total"],
              "failures": [dict(f) for f in res["failures"][:MAX_RECORDED_FAILURES]],
              "explanation": None}
    if res["failures"] and attempt < MAX_ATTEMPTS:
        try:
            verdict = agents.explain_divergence(state["spec"], state["cobol_src"],
                                                state.get("python_src") or "", res["failures"][0])
            record["explanation"] = {"verdict": verdict.get("verdict"), "reason": verdict.get("reason"),
                                     "input": res["failures"][0]["input"]}
        except Exception as e:  # the explanation is a bonus; the retry goes ahead without it
            record["explanation"] = {"verdict": None, "reason": f"explainer unavailable: {type(e).__name__}",
                                     "input": res["failures"][0]["input"]}
    return record


@_safe("accept")
def accept(state: GraphState) -> GraphState:
    # unit tests are a bonus layer: failures here don't block acceptance
    try:
        UNIT_DIR.mkdir(parents=True, exist_ok=True)
        tests_src = agents.write_unit_tests(state["spec"], state["python_src"])
        (UNIT_DIR / f"test_{state['id']}_unit.py").write_text(tests_src)
        note = "unit tests written"
        unit_status = 'fixture' if os.getenv('LLM_MODE') == 'fake' else 'passed'
    except Exception as e:
        quarantined = list(getattr(e, "quarantined", []) or [])
        if getattr(e, "code", None):
            # passing tests are kept; disputed ones stay in the file, visibly skipped
            (UNIT_DIR / f"test_{state['id']}_unit.py").write_text(e.code)
            note = (f"unit tests written; {len(quarantined)} quarantined for review: "
                    f"{', '.join(quarantined)}")
        else:
            note = f"unit test writer failed: {e}"
        unit_status = 'needs_review'
        state = {**state, "unit_tests_quarantined": quarantined}
    out = {**state, "status": "done", "last_failures": [], 'unit_tests_status': unit_status}
    hinted = "; a human hint guided the rewrite" if state.get("human_hints") else ""
    status.update(out, "accept", f"verified identical. {note}{hinted}")
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
