"""Exercise Hemant's actual graph in a disposable merged checkout, using agent fixtures."""
import argparse
import inspect
import json
import os
from pathlib import Path
import re
import sys


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('team_root', type=Path, help='DISPOSABLE team checkout with P2 files overlaid')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.team_root.resolve()
    require(not (root / 'legacy.py').exists(), 'Remove the legacy.py stub; use the real legacy/ package')
    require({p.stem.lower() for p in (root / 'legacy').glob('*.cbl')} == {'interest', 'payroll', 'invoice'},
            'Move the HELLO.cbl placeholder outside legacy/; exactly three demo originals are required')
    os.environ.update(LLM_MODE='fake', LANGCHAIN_TRACING_V2='false', LANGSMITH_TRACING='false')
    sys.path.insert(0, str(root))
    import agents
    import contract
    import legacy
    import testing
    from pipeline import graph, status
    require(Path(legacy.__file__).resolve() == root / 'legacy/__init__.py', 'Wrong legacy import')
    require(Path(testing.__file__).resolve() == root / 'testing.py', 'Wrong testing import')
    require(contract.TestResult.__required_keys__ == {'passed', 'total', 'failures'}, 'TestResult shape changed')
    require(contract.GoldenCase.__required_keys__ == {'input', 'output'}, 'Golden schema changed')
    for function, names in [(legacy.compile_cobol, ['cobol_path']),
                            (legacy.run_cobol, ['binary_path', 'input_line']),
                            (legacy.record_golden, ['module_id', 'binary_path', 'inputs']),
                            (testing.golden_to_pytest, ['module_id', 'py_module_path']),
                            (testing.run_equivalence, ['module_id'])]:
        require(list(inspect.signature(function).parameters) == names, f'Signature mismatch: {function}')
    ids = ['interest', 'payroll', 'invoice']
    discovered = agents.understand(str(root / 'legacy'))
    require({module['module_id'] for module in discovered} == set(ids), 'Discovery did not find the originals')
    fixtures = {mid: (root / f'tests/fixtures/{mid}_reference.py').read_text() for mid in ids}
    inputs = {mid: json.loads((root / f'legacy/inputs/{mid}.json').read_text()) for mid in ids}
    mode = {'name': 'happy'}
    def identify(source):
        return re.search(r'program-id\.\s*([a-z]+)', source, flags=re.I).group(1).lower()
    def generate(spec, source):
        return [] if mode['name'] == 'empty' else inputs[identify(source)]
    def rewrite(spec, source, failures):
        mid = identify(source)
        if mode['name'] == 'flood':
            return 'import os\ndef main(line):\n    while True: os.write(1, b"x" * 8192)\n'
        if mid == 'invoice' and (mode['name'] == 'exhaust' or mode['name'] == 'repair' and not failures):
            return fixtures[mid].replace('ROUND_DOWN', 'ROUND_HALF_UP')
        return fixtures[mid]
    agents.generate_inputs = generate
    agents.rewrite = rewrite
    agents.write_unit_tests = lambda spec, source: '# Audit fixture: unit-test agent not exercised.\n'
    agents.explain_divergence = lambda spec, src, py, failure: {
        'verdict': 'legacy_quirk', 'reason': 'Audit fixture: COBOL truncates fractional cents.'}
    graph.MAX_ATTEMPTS = 3
    report = {'mode': 'actual_hemant_graph_with_handwritten_agents',
              'models_called': False, 'real_agent_prompts_tested': False,
              'graph_path': 'pipeline/graph.py', 'scenarios': {}}
    def run(mid):
        source = root / f'legacy/{mid}.cbl'
        final = graph.build_graph().invoke({'id': mid, 'cobol_path': str(source),
                    'cobol_src': source.read_text(), 'attempts': 0,
                    'last_failures': [], 'divergences': []})
        saved = json.loads(status.STATE_PATH.read_text())['modules'][mid]
        require(saved['status'] == final['status'], 'State persistence disagrees with graph')
        return {key: final.get(key) for key in ('id', 'status', 'attempts', 'tests_passed',
                                               'tests_total', 'last_failures', 'divergences', 'error')}
    status.start_run(ids)
    happy = [run(mid) for mid in ids]
    require(all(row['status'] == 'done' and row['tests_passed'] == row['tests_total'] == 15 for row in happy),
            f'Happy path failed: {happy}')
    report['scenarios']['all_three_accept'] = happy
    mode['name'] = 'repair'; status.start_run(['invoice'])
    repaired = run('invoice')
    require(repaired['status'] == 'done' and repaired['attempts'] == 2 and repaired['tests_passed'] == 15,
            f'Retry did not repair: {repaired}')
    report['scenarios']['rounding_retry_repair'] = repaired
    mode['name'] = 'exhaust'; status.start_run(['invoice'])
    failed = run('invoice')
    require(failed['status'] == 'failed' and failed['attempts'] == 3 and len(failed['divergences']) == 2,
            f'Retry limit/explanation route failed: {failed}')
    report['scenarios']['three_attempts_then_explain_fixture'] = failed
    mode['name'] = 'empty'; status.start_run(['interest'])
    empty = run('interest')
    require(empty['status'] == 'failed' and 'record:' in empty['error'], f'Empty input accepted: {empty}')
    report['scenarios']['empty_inputs_fail_closed'] = empty
    mode['name'] = 'flood'; status.start_run(['interest'])
    flood = run('interest')
    require(flood['status'] == 'failed' and 'output exceeded' in flood['error'], f'Flood did not fail closed: {flood}')
    report['scenarios']['output_flood_fail_closed'] = flood
    report['status'] = 'passed'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'scenarios': list(report['scenarios']), 'report': str(args.output)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
