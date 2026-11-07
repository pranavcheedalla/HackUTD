"""CONTROLLED MUTATION: prove verify -> explain -> repair catches invoice rounding.

    python tools/mutation_check.py runs/sessions/<accepted-session> [--attempts 3]

The accepted session is never modified. It is copied to <session>-mutation, where the
accepted modern/invoice.py is deliberately changed to round half-up instead of truncating
(a labeled, injected bug: the model got truncation right on its own). The tool then:

  1. verifies the mutant against the recorded COBOL goldens (must FAIL, incl. 12.35 -> 12.34),
  2. asks the real explanation agent why the first mismatch happened,
  3. runs the real rewrite agent with those failures, up to --attempts times, until it passes.

Evidence is written to <copy>/runs/mutation_check.json; model calls go to its llm_calls.jsonl.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = 'rounding=ROUND_HALF_UP if rounded else ROUND_DOWN'
MUTANT = 'rounding=ROUND_HALF_UP'
HEADER = '# CONTROLLED MUTATION: pic_store always rounds half-up (injected bug, not model output)\n'


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify(source: str, cases: list[dict], scratch: Path, name: str) -> list[dict]:
    path = scratch / f'{name}.py'
    path.write_text(source)
    try:
        module = load(path, name)
    except Exception as error:  # noqa: BLE001
        return [{'input': c['input'], 'expected': c['output'], 'actual': f'<import error: {error}>'} for c in cases]
    failures = []
    for case in cases:
        try:
            actual = module.main(case['input'])
        except Exception as error:  # noqa: BLE001
            actual = f'<exception: {type(error).__name__}: {error}>'
        if actual != case['output']:
            failures.append({'input': case['input'], 'expected': case['output'], 'actual': actual})
    return failures


def inner(attempts: int) -> int:
    sys.path.insert(0, str(Path.cwd()))
    import agents

    accepted = Path('modern/invoice.py').read_text()
    if ORIGINAL not in accepted:
        print('accepted invoice.py lacks the expected truncation line; cannot inject mutation')
        return 2
    mutant = HEADER + accepted.replace(ORIGINAL, MUTANT).replace(
        'from decimal import Decimal, ROUND_DOWN', 'from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP')
    cases = [json.loads(line) for line in Path('golden/invoice.jsonl').read_text().splitlines() if line.strip()]
    spec = json.loads(Path('specs/invoice.json').read_text())
    cobol = Path('legacy/invoice.cbl').read_text()
    scratch = Path('runs/mutation'); scratch.mkdir(parents=True, exist_ok=True)
    Path(scratch / 'invoice_mutant.py').write_text(mutant)

    evidence: dict = {'label': 'CONTROLLED MUTATION (injected rounding bug, not a model output)',
                      'cases': len(cases)}
    failures = verify(mutant, cases, scratch, 'invoice_mutant')
    caught = [f for f in failures if f['expected'] == 'TOTAL=00012.34' and f['actual'] == 'TOTAL=00012.35']
    evidence['mutant'] = {'failed': len(failures), 'caught_12_35': bool(caught), 'failures': failures}
    print(f'mutant: {len(cases) - len(failures)}/{len(cases)} passed; 12.34 vs 12.35 caught: {bool(caught)}')
    if not failures or not caught:
        evidence['result'] = 'verification did not catch the mutation'
        Path('runs/mutation_check.json').write_text(json.dumps(evidence, indent=1))
        return 1

    first = caught[0]
    explanation = agents.explain_divergence(spec, cobol, mutant, first)
    evidence['explanation'] = {'failure': first, **explanation}
    print(f"explain: {explanation.get('verdict')}: {explanation.get('reason')}")

    previous, current = mutant, failures
    evidence['repairs'] = []
    for attempt in range(1, attempts + 1):
        candidate = agents.rewrite(spec, cobol, current, previous)
        current = verify(candidate, cases, scratch, f'invoice_repair_{attempt}')
        (scratch / f'invoice_repair_{attempt}.py').write_text(candidate)
        evidence['repairs'].append({'attempt': attempt, 'failed': len(current)})
        print(f'repair attempt {attempt}: {len(cases) - len(current)}/{len(cases)} passed')
        if not current:
            break
        previous = candidate
    evidence['result'] = 'repaired' if not current else f'not repaired after {attempts} attempts'
    Path('runs/mutation_check.json').write_text(json.dumps(evidence, indent=1))
    print(evidence['result'])
    return 0 if not current else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('session', type=Path, nargs='?')
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--inner', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inner:
        return inner(args.attempts)
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    if not os.getenv('NVIDIA_API_KEY', '').startswith('nvapi-'):
        parser.error('Configure NVIDIA_API_KEY in the local .env first')
    session = args.session.resolve()
    copy = session.with_name(session.name + '-mutation')
    if copy.exists():
        shutil.rmtree(copy)
    shutil.copytree(session, copy, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    (copy / 'runs' / 'llm_calls.jsonl').unlink(missing_ok=True)
    shutil.copy2(Path(__file__).resolve(), copy / 'tools' / 'mutation_check.py')
    print(f'Mutation copy: {copy}')
    environment = dict(os.environ, LLM_MODE='real', LANGCHAIN_TRACING_V2='false', LANGSMITH_TRACING='false')
    return subprocess.call([sys.executable, str(copy / 'tools' / 'mutation_check.py'), '--inner',
                            '--attempts', str(args.attempts)], cwd=copy, env=environment)


if __name__ == '__main__':
    raise SystemExit(main())
