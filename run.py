"""
P1 (Hemant) — entry point.

    python run.py                 # all modules in legacy/
    python run.py legacy/ --only payroll
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
    modules = agents.understand(args.legacy_dir)
    if args.only:
        modules = [m for m in modules if m["module_id"] == args.only]
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
                "cobol_src": Path(m["cobol_path"]).read_text(errors="ignore"),
                "attempts": 0, "divergences": [], "last_failures": []}
        final = graph.invoke(init)
        results[m["module_id"]] = final
        print(f"  -> {final['status']}  ({final.get('tests_passed', 0)}/{final.get('tests_total', 0)} tests, "
              f"{final.get('attempts', 0)} attempts)" + (f"  error: {final['error']}" if final.get("error") else ""))

    done = sum(r["status"] == "done" for r in results.values())
    print(f"\n{done}/{len(results)} modules verified. Live state: runs/state.json")
    return 0 if done == len(results) else 2


if __name__ == "__main__":
    sys.exit(main())
