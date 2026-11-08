"""Combined P1 graph and real P2 runtime, exercised through the public CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def project(tmp_path):
    copy = tmp_path / 'combined project with spaces'
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(
        '.git', '.env', '__pycache__', '.pytest_cache', '.cache', '.venv',
        'bin', 'runs', 'modern', 'specs', 'equivalence', 'unit', 'validation',
    ))
    return copy


def invoke(project, *arguments, mode='fake'):
    environment = dict(os.environ, LLM_MODE=mode, MAX_ATTEMPTS='3', LANGCHAIN_TRACING_V2='false', LANGSMITH_TRACING='false')
    environment.pop('NVIDIA_API_KEY', None)
    return subprocess.run([sys.executable, str(project / 'run.py'), *arguments],
                          cwd=project.parent, env=environment, capture_output=True,
                          text=True, timeout=60)


def test_all_three_run_through_real_graph_and_repair_invoice(project):
    saved = {mid: (project / f'golden/{mid}.jsonl').read_bytes() for mid in ('interest', 'payroll', 'invoice')}
    result = invoke(project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'OFFLINE FIXTURE DEMO' in result.stdout
    state = json.loads((project / 'runs/state.json').read_text())
    assert state['mode'] == 'offline_fixture'
    assert set(state['modules']) == set(saved)
    assert all(value['status'] == 'done' and value['tests_passed'] == value['tests_total'] == 15
               for value in state['modules'].values())
    assert state['modules']['invoice']['attempts'] == 2
    assert any(event['node'] == 'verify' and '13/15' in event['msg'] for event in state['events'])
    assert all((project / f'golden/{mid}.jsonl').read_bytes() == data for mid, data in saved.items())
    assert not (project / 'legacy.py').exists()
    assert len(list((project / 'legacy').glob('*.cbl'))) == 3


def test_exhaustion_reaches_explanation_and_failure(project):
    result = invoke(project, '--only', 'invoice', '--demo-scenario', 'exhaust')
    assert result.returncode == 2, result.stdout + result.stderr
    module = json.loads((project / 'runs/state.json').read_text())['modules']['invoice']
    assert module['status'] == 'failed' and module['attempts'] == 3
    assert module['tests_passed'] == 13 and module['tests_total'] == 15
    assert len(module['divergences']) == 2
    assert all(case['verdict'] == 'legacy_quirk' for case in module['divergences'])


def test_real_mode_refuses_stubs_before_calls_or_state_mutation(project):
    result = invoke(project, mode='real')
    assert result.returncode == 2
    assert 'Real run blocked' in result.stderr
    assert not (project / 'runs/state.json').exists()


def test_unknown_module_selection_is_clear(project):
    result = invoke(project, '--only', 'missing')
    assert result.returncode == 1
    assert "Unknown module 'missing'" in result.stderr


def test_invalid_mode_is_rejected(project):
    result = invoke(project, mode='typo')
    assert result.returncode == 2
    assert 'LLM_MODE must be fake or real' in result.stderr
