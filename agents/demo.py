"""Explicit offline agents for the three P2 samples. Never calls a model."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
MODULES = {'interest', 'payroll', 'invoice'}


def _id(source):
    match = re.search(r'program-id\.\s*([a-z]+)', source, flags=re.I)
    mid = match.group(1).lower() if match else ''
    if mid not in MODULES:
        raise ValueError(f'Offline fixtures support only {sorted(MODULES)}; got {mid!r}')
    return mid


def understand(legacy_dir):
    modules = []
    for path in sorted(Path(legacy_dir).glob('*.cbl')):
        mid = _id(path.read_text())
        if mid != path.stem.lower():
            raise ValueError(f'Demo source ID does not match filename: {path}')
        modules.append({'module_id': mid, 'cobol_path': str(path.resolve()), 'depends_on': []})
    return modules


def extract_spec(source):
    mid = _id(source)
    rules = {
        'interest': ['principal * annual_rate_percent * years / 100; round half-up to cents'],
        'payroll': ['Regular pay through 40 hours; overtime 1.5x',
                    'Progressive demo tax: first 500 at 10%, next 500 at 20%, rest at 30%',
                    'Round gross, then tax, then subtract'],
        'invoice': ['quantity * unit_price * (100 - discount_percent) / 100',
                    'Reject exact totals >= 100000; truncate fractional cents in PIC 9(5)V99'],
    }
    formats = {'interest': 'principal|rate_percent|years', 'payroll': 'hours|hourly_rate',
               'invoice': 'quantity|unit_price|discount_percent'}
    return {'module_id': mid, 'summary': f'[OFFLINE FIXTURE] {mid}; no model-generated spec',
            'inputs': [{'name': 'input_line', 'type': 'string', 'format': formats[mid]}],
            'outputs': [{'name': 'result', 'type': 'string', 'format': 'exact COBOL DISPLAY format'}],
            'business_rules': rules[mid], 'edge_cases': ['zero', 'negative', 'maximum', 'invalid syntax'],
            'quirks': ['PIC 9(5)V99 truncates fractional cents'] if mid == 'invoice' else []}


def generate_inputs(spec, source):
    return json.loads((ROOT / f'legacy/inputs/{_id(source)}.json').read_text())


def install(agents, scenario='repair'):
    """Select demo functions only in the dedicated CLI process's fake mode."""
    if scenario not in ('repair', 'exhaust'):
        raise ValueError('Unknown demo scenario')
    def rewrite(spec, source, failures):
        mid = _id(source)
        fixture = (ROOT / f'tests/fixtures/{mid}_reference.py').read_text()
        if mid == 'invoice' and (scenario == 'exhaust' or not failures):
            return fixture.replace('ROUND_DOWN', 'ROUND_HALF_UP')
        return fixture
    def explain(spec, source, python_source, failure):
        return {'verdict': 'legacy_quirk',
                'reason': '[OFFLINE FIXTURE] COBOL truncates fractional cents; the rewrite rounded them.'}
    agents.understand = understand
    agents.extract_spec = extract_spec
    agents.generate_inputs = generate_inputs
    agents.rewrite = rewrite
    agents.explain_divergence = explain
    agents.write_unit_tests = lambda spec, source: '# OFFLINE FIXTURE: real unit-test agent not exercised.\n'
