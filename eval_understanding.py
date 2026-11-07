"""Eyeball eval for P3's agents: understand -> extract_spec -> generate_inputs on every program.

    python eval_understanding.py                        # samples/legacy, real Nemotron calls
    python eval_understanding.py path/to/legacy         # P2's programs
    python eval_understanding.py --offline              # no API key needed (fake LLM)
    python eval_understanding.py --only invoice --save  # one module, write specs/ + inputs/
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from agents import _llm
from agents.cobol_static import analyze
from agents.extract_spec import extract_spec, validate_spec
from agents.generate_inputs import LAST_RUN, generate_inputs
from agents.understand import load_cobol_source, understand


def rule(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("legacy_dir", nargs="?", default="samples/legacy")
    ap.add_argument("--offline", action="store_true", help="use the fake LLM (no API key)")
    ap.add_argument("--only", help="run a single module_id")
    ap.add_argument("--no-inputs", action="store_true", help="skip generate_inputs (saves Super calls)")
    ap.add_argument("--save", action="store_true", help="write specs/<id>.json and inputs/<id>.json")
    args = ap.parse_args()

    if args.offline:
        sys.path.insert(0, str(Path(__file__).parent / "tests"))
        from fake_llm import fake_call_llm

        _llm.call_llm = fake_call_llm

    rule("PHASE 1  understand()  - dependency order, leaves first")
    modules = understand(args.legacy_dir)
    for i, m in enumerate(modules, 1):
        print(f"{i}. {m['module_id']:<14} {m['cobol_path']:<40} depends_on={m['depends_on']} "
              f"copybooks={[Path(c).name for c in m['copybooks']]}")

    for m in modules:
        if args.only and m["module_id"] != args.only:
            continue
        src = load_cobol_source(m["cobol_path"])
        a = analyze(src)

        rule(f"PHASE 2  extract_spec({m['module_id']})")
        t = time.time()
        spec = extract_spec(src)
        spec["module_id"] = m["module_id"]  # what the pipeline will do
        errors = validate_spec(spec)
        print(json.dumps(spec, indent=2))
        print(f"\nschema: {'OK' if not errors else errors}   time: {time.time() - t:.1f}s")
        print(f"static truncation targets: {a.truncation_targets or 'none'}")
        added = [q for q in spec["quirks"] if q.startswith("[static check")]
        if added:
            print(f"!! model missed {len(added)} truncation quirk(s); added by the static check")

        inputs = []
        if not args.no_inputs and a.accept_targets:
            rule(f"PHASE 3  generate_inputs({m['module_id']})  record width = {a.input_width or '?'}")
            t = time.time()
            inputs = generate_inputs(spec, src)
            for i, c in enumerate(LAST_RUN["cases"], 1):
                print(f"{i:3}. {c['input']!r:<34} {c['covers']}")
            print(f"\n{len(inputs)} inputs, {len(LAST_RUN['warnings'])} warnings, {time.time() - t:.1f}s")
        elif not a.accept_targets:
            print("\n(no ACCEPT - subprogram, skipping generate_inputs)")

        if args.save:
            Path("specs").mkdir(exist_ok=True)
            Path(f"specs/{m['module_id']}.json").write_text(json.dumps(spec, indent=2))
            if inputs:
                Path("inputs").mkdir(exist_ok=True)
                Path(f"inputs/{m['module_id']}.json").write_text(json.dumps(inputs, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
