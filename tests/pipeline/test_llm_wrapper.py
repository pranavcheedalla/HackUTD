"""P1 wrapper behavior with mocked model responses; no NVIDIA calls or keys."""
from types import SimpleNamespace
import llm


def configure(monkeypatch, tmp_path):
    monkeypatch.setenv('LLM_MODE', 'real')
    monkeypatch.setattr(llm, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(llm, 'USE_CACHE', True)


def test_response_cache_avoids_repeat_model_call(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    calls = []
    def invoke(*arguments):
        calls.append(arguments)
        return 'answer'
    monkeypatch.setattr(llm, '_invoke', invoke)
    assert llm.call_llm('nano', 'system', 'question') == 'answer'
    assert llm.call_llm('nano', 'system', 'question') == 'answer'
    assert len(calls) == 1


def test_invalid_json_schema_response_gets_one_repair(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    responses = iter(['{"wrong":1}', '{"module_id":"interest"}'])
    calls = []
    def invoke(*arguments):
        calls.append(arguments)
        return next(responses)
    monkeypatch.setattr(llm, '_invoke', invoke)
    result = llm.call_llm('nano', 'system', 'question',
                          json_schema={'type': 'object', 'required': ['module_id']})
    assert result == {'module_id': 'interest'}
    assert len(calls) == 2 and 'previous reply was invalid' in calls[1][2]


def test_api_retry_backoff_and_reasoning_strip_are_mocked(monkeypatch):
    client_calls = []
    sleeps = []
    class Client:
        def invoke(self, messages):
            client_calls.append(messages)
            if len(client_calls) < 3:
                raise RuntimeError('simulated transient error')
            return SimpleNamespace(content='<think>private reasoning</think>answer')
    monkeypatch.setattr(llm, '_client', lambda model: Client())
    monkeypatch.setattr(llm, 'MAX_RETRIES', 3)
    monkeypatch.setattr(llm.time, 'sleep', sleeps.append)
    assert llm._invoke('nano', 'system', 'question') == 'answer'
    assert sleeps == [2.0, 4.0] and len(client_calls) == 3
