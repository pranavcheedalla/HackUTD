"""Integration regressions found while combining the real P3/P4 branches."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import llm
from agents import _llm
from agents.cobol_static import analyze, render_summary
from agents._sandbox import run_main
from ui.dashboard_data import artifact, session_root

ROOT = Path(__file__).resolve().parents[2]
gi = importlib.import_module('agents.generate_inputs')
es = importlib.import_module('agents.extract_spec')


@pytest.mark.parametrize('module_id,count', [('interest', 3), ('invoice', 3), ('payroll', 2)])
def test_delimited_input_is_not_a_256_column_record(module_id, count):
    analysis = analyze((ROOT / f'legacy/{module_id}.cbl').read_text())
    assert analysis.delimiter == '|'
    assert analysis.input_width == 0 and analysis.input_layout == []
    assert len(analysis.delimited_fields) == count
    assert all(f['type'] in ('decimal', 'integer') for f in analysis.delimited_fields)
    assert 'literal decimal points are typed' in render_summary(analysis)


def test_invoice_move_truncation_is_preserved_even_if_model_misses_it(monkeypatch):
    monkeypatch.setenv('LLM_MODE', 'fake')
    monkeypatch.setattr(_llm, 'call_llm', lambda *a: 'garbage')
    source = (ROOT / 'legacy/invoice.cbl').read_text()
    assert 'INVOICE-TOTAL' in analyze(source).truncation_targets
    spec = es.extract_spec(source)
    assert len(spec['inputs']) == 3
    assert any('INVOICE-TOTAL' in q and 'TRUNCATED' in q for q in spec['quirks'])


@pytest.mark.parametrize('module_id', ['interest', 'invoice', 'payroll'])
def test_reviewed_inputs_survive_model_proposals_and_case_cap(monkeypatch, module_id):
    monkeypatch.setenv('LLM_MODE', 'real')
    monkeypatch.setattr(_llm, 'call_llm', lambda *a: {'cases': [
        {'input': f'{i}|1.00' + ('' if module_id == 'payroll' else '|1'), 'covers': 'normal'}
        for i in range(1, 40)]})
    source = (ROOT / f'legacy/{module_id}.cbl').read_text()
    reviewed = json.loads((ROOT / f'legacy/inputs/{module_id}.json').read_text())
    inputs = gi.generate_inputs({}, source)
    assert 20 <= len(inputs) <= 30 and len(inputs) == len(set(inputs))
    assert set(reviewed) <= set(inputs)
    assert all('|' in x and len(x) < 256 for x in inputs)


@pytest.mark.parametrize('agent', [es, gi])
def test_real_mode_does_not_disguise_api_failure_with_offline_fallback(monkeypatch, agent):
    monkeypatch.setenv('LLM_MODE', 'real')
    def fail(*a):
        raise RuntimeError('HTTP 401 unauthorized')
    monkeypatch.setattr(_llm, 'call_llm', fail)
    with pytest.raises(RuntimeError, match='401'):
        agent._call('s', 'u', {})


def test_real_mode_rejects_short_input_set(monkeypatch):
    monkeypatch.setenv('LLM_MODE', 'real')
    monkeypatch.setattr(_llm, 'call_llm', lambda *a: {'cases': []})
    with pytest.raises(ValueError, match='no usable input proposals'):
        gi.generate_inputs({}, (ROOT / 'legacy/invoice.cbl').read_text())


def test_schema_is_sent_to_nvidia_not_only_written_in_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv('LLM_MODE', 'real')
    monkeypatch.setattr(llm, 'USE_CACHE', False)
    monkeypatch.setattr(llm, 'TRACE_PATH', tmp_path / 'trace')
    bound = []
    class Client:
        def bind(self, **kwargs):
            bound.append(kwargs)
            return self
        def invoke(self, messages):
            return SimpleNamespace(content='{"a": 1}')
    monkeypatch.setattr(llm, '_client', lambda model: Client())
    schema = {'type': 'object', 'required': ['a'], 'properties': {'a': {'type': 'integer'}}}
    assert llm.call_llm('nano', 's', 'u', schema) == {'a': 1}
    assert bound[0]['response_format']['json_schema']['schema'] == schema
    assert llm._schema_context.get() is None


@pytest.mark.parametrize('status', [400, 401, 403, 404, 410])
def test_permanent_http_errors_are_not_retried(monkeypatch, status):
    class Client:
        def invoke(self, messages):
            raise RuntimeError(f'[{status}] rejected')
    monkeypatch.setattr(llm, '_client', lambda model: Client())
    monkeypatch.setattr(llm.time, 'sleep', lambda _: pytest.fail('Permanent errors must not sleep'))
    with pytest.raises(llm.LLMError, match='rejected'):
        llm._invoke('nano', 's', 'u')


def test_empty_answers_are_not_cached(monkeypatch, tmp_path):
    monkeypatch.setenv('LLM_MODE', 'real')
    monkeypatch.setattr(llm, 'CACHE_DIR', tmp_path / 'cache')
    monkeypatch.setattr(llm, 'TRACE_PATH', tmp_path / 'trace')
    monkeypatch.setattr(llm, '_invoke', lambda *a: '')
    with pytest.raises(llm.LLMError, match='empty'):
        llm.call_llm('nano', 's', 'u')
    assert not list((tmp_path / 'cache').glob('*.json'))


def test_dataclass_rewrite_can_be_imported_by_p4_smoke_check():
    result = run_main('from dataclasses import dataclass\n@dataclass\nclass A:\n    x: str\ndef main(s):\n    return A(s).x\n', ['ok'])
    assert result['results'][0]['output'] == 'ok'


def test_p4_smoke_check_bounds_generated_output():
    result = run_main('print("x" * 3000000)\ndef main(s):\n    return s\n', ['ok'])
    assert 'output limit' in result['import_error']


def test_dashboard_rejects_file_and_session_traversal(tmp_path):
    assert artifact(tmp_path, 'modern', '../.env', '.py') == 'Invalid module id'
    with pytest.raises(ValueError):
        artifact(tmp_path, '.', 'interest', '')
    with pytest.raises(ValueError):
        session_root(tmp_path, '../../')


def test_dashboard_renders_without_calls_or_credentials(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.delenv('NVIDIA_API_KEY', raising=False)
    app = AppTest.from_file(str(ROOT / 'ui/app.py')).run(timeout=15)
    assert not app.exception
    assert app.title[0].value == 'Legacy → Verified'
    assert any(button.label == 'Start pipeline' for button in app.button)
