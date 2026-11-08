"""
P1 (Hemant) — entry point.

    python run.py                 # all modules in legacy/
    python run.py legacy/ --only payroll
    python run.py samples/legacy --only invoice   # also runs invoice's dependencies first
    LLM_MODE=fake python run.py   # stub run, no API calls
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import agents  # noqa: E402
import legacy  # noqa: E402
import testing  # noqa: E402
from pipeline import status  # noqa: E402
from pipeline.graph import build_graph  # noqa: E402
from agents.understand import load_cobol_source  # noqa: E402


def stub_report() -> list[str]:
    import agents.building as b
    import agents.understanding as u
    stubs = [name for name, mod in [("legacy (P2)", legacy), ("testing (P2)", testing),
                                    ("understanding agents (P3)", u), ("building agents (P4)", b)]
             if getattr(mod, "STUB", False)]
    if stubs:
        print("Using STUBS for: " + ", ".join(stubs))
    return stubs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("legacy_dir", nargs="?", default=str(ROOT / "legacy"))
    ap.add_argument("--only", help="run a single module id")
    ap.add_argument('--demo-scenario', choices=('repair', 'exhaust'),
                    help='fake mode: invoice repairs on retry or exhausts three attempts')
    args = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env')
    except ImportError:
        pass
    mode = os.getenv('LLM_MODE', 'real').lower()
    if mode not in ('fake', 'real'):
        ap.error('LLM_MODE must be fake or real')
    stubs = stub_report()
    if mode == 'fake':
        from agents.demo import install
        install(agents, args.demo_scenario or 'repair')
        print('OFFLINE FIXTURE DEMO: real COBOL and LangGraph; no model calls.')
    else:
        if args.demo_scenario:
            ap.error('--demo-scenario requires LLM_MODE=fake')
        if stubs:
            print('Real run blocked: merge the real agent implementations first. '
                  'For the offline fixture demo use LLM_MODE=fake.', file=sys.stderr)
            return 2
        if not os.getenv('NVIDIA_API_KEY') or os.getenv('NVIDIA_API_KEY') in ('nvapi-...', 'your-key-here'):
            print('Real run blocked: configure NVIDIA_API_KEY in the local .env. '
                  'Use LLM_MODE=fake for the labeled fixture demo.', file=sys.stderr)
            return 2
        if os.getenv('P4_FORCE_LOCAL_LLM') == '1':
            print('Real run blocked: unset P4_FORCE_LOCAL_LLM so all agents use the shared client.', file=sys.stderr)
            return 2
        try:
            import langchain_nvidia_ai_endpoints  # noqa: F401
        except ImportError:
            print('Real run blocked: install requirements.txt in your virtual environment.', file=sys.stderr)
            return 2
    if not Path(args.legacy_dir).is_dir():
        print(f"Legacy folder not found: {args.legacy_dir}", file=sys.stderr)
        return 1
    modules = agents.understand(args.legacy_dir)
    by_id = {m["module_id"]: m for m in modules}
    if args.only and args.only not in by_id:
        print(f"Unknown module {args.only!r}. Modules in {args.legacy_dir}: "
              f"{', '.join(by_id) or '(none)'}", file=sys.stderr)
        return 1
    if args.only:
        # also run X's dependencies (transitively), else X is always blocked
        wanted, todo = set(), [args.only]
        while todo:
            mid = todo.pop()
            if mid in by_id and mid not in wanted:
                wanted.add(mid)
                todo += by_id[mid].get("depends_on", [])
        modules = [m for m in modules if m["module_id"] in wanted]
    if not modules:
        print(f"No .cbl modules found in {args.legacy_dir}")
        return 1

    order = [m["module_id"] for m in modules]
    print("Migration order:", " -> ".join(order))
    status.start_run(order)
    status.set_mode('offline_fixture' if mode == 'fake' else 'real_model')
    graph = build_graph()

    results = {}
    for m in modules:
        print(f"\n=== {m['module_id']} ===")
        init = {"id": m["module_id"], "cobol_path": m["cobol_path"],
                "cobol_src": load_cobol_source(m["cobol_path"]),  # copybooks pasted inline (P3)
                "attempts": 0, "divergences": [], "last_failures": [],
                # codebase support (P3 keys; defaults keep pre-merge understand() working)
                "kind": m.get("kind", "program"), "program_id": m.get("program_id", ""),
                "link": m.get("link", []), "copy_dirs": m.get("copy_dirs", []),
                "params": m.get("params", []), "depends_on": m.get("depends_on", []),
                "dep_modules": [{"module_id": d, "program_id": by_id.get(d, {}).get("program_id", ""),
                                 "params": by_id.get(d, {}).get("params", []),
                                 "status": results.get(d, {}).get("status", "not run")}
                                for d in m.get("depends_on", [])]}
        blocked = next((d["module_id"] for d in init["dep_modules"] if d["status"] != "done"), None)
        if blocked:
            # skip the graph entirely: no model calls for a module whose callee isn't verified
            final = {**init, "status": "failed", "error": f"blocked: dependency {blocked} not verified"}
            status.update(final, "blocked", final["error"])
            results[m["module_id"]] = final
            print(f"  -> failed  {final['error']}")
            continue
        final = graph.invoke(init)
        results[m["module_id"]] = final
        print(f"  -> {final['status']}  ({final.get('tests_passed', 0)}/{final.get('tests_total', 0)} tests, "
              f"{final.get('attempts', 0)} attempts)" + (f"  error: {final['error']}" if final.get("error") else ""))

    done = sum(r["status"] == "done" for r in results.values())
    print(f"\n{done}/{len(results)} modules verified. Live state: runs/state.json")
    return 0 if done == len(results) else 2


if __name__ == "__main__":
    sys.exit(main())
