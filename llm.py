"""
P1 (Hemant) — the ONE way every agent talks to Nemotron.

    from llm import call_llm
    spec = call_llm("nano", SYSTEM, cobol_src, json_schema=SPEC_SCHEMA)   # -> dict
    code = call_llm("super", SYSTEM, prompt)                               # -> str

Features
- Nano / Super picked by name; real model IDs come from .env
- Retries with exponential backoff on API errors
- JSON mode: parses the reply, validates against the schema, and on failure
  retries once with the validation error so the model can repair it
- Disk cache keyed on (model, system, user, schema): repeat runs are instant
  and free, and the demo can replay from cache if the API is slow
- LLM_MODE=fake skips the API entirely (for stub runs / no key yet)
"""
from __future__ import annotations

import hashlib
import contextvars
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / '.env')
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / ".cache" / "llm"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Verify the exact IDs on build.nvidia.com and put them in .env
MODEL_IDS = {
    "nano": os.getenv("NEMOTRON_NANO_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"),
    "super": os.getenv("NEMOTRON_SUPER_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b"),
}
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "4"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "16384"))
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
THINKING = os.getenv("NEMOTRON_THINKING", "0") == "1"
TRACE_PATH = ROOT / 'runs' / 'llm_calls.jsonl'
USE_CACHE = os.getenv("LLM_CACHE", "1") != "0"

_clients: dict[str, Any] = {}
_schema_context = contextvars.ContextVar('llm_schema', default=None)


class LLMError(RuntimeError):
    pass


def _mode() -> str:
    return os.getenv("LLM_MODE", "real").lower()


def _client(model: str):
    if model not in _clients:
        key = os.getenv("NVIDIA_API_KEY")
        if not key:
            raise LLMError("NVIDIA_API_KEY missing. Put it in .env or set LLM_MODE=fake.")
        from langchain_nvidia_ai_endpoints import ChatNVIDIA
        kwargs = dict(model=MODEL_IDS[model], api_key=key,
                      temperature=TEMPERATURE, max_completion_tokens=MAX_TOKENS, timeout=TIMEOUT)
        base_url = os.getenv("NVIDIA_BASE_URL")  # set for local vLLM/Ollama, else hosted NIM
        if base_url:
            kwargs["base_url"] = base_url
        _clients[model] = ChatNVIDIA(**kwargs).bind(chat_template_kwargs={'enable_thinking': THINKING})
    return _clients[model]


def _cache_key(model: str, system: str, user: str, schema: Optional[dict]) -> str:
    blob = json.dumps([MODEL_IDS[model], system, user, schema], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def _strip_reasoning(text: str) -> str:
    # Nemotron reasoning models may emit <think>...</think> before the answer
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    if '</think>' in text:
        text = text.split('</think>', 1)[1]
    # An unfinished reasoning block is not an answer.
    return text.split('<think>', 1)[0].strip()


def _safe_error(error: Exception) -> str:
    text = f'{type(error).__name__}: {error}'
    key = os.getenv('NVIDIA_API_KEY')
    if key:
        text = text.replace(key, '[REDACTED]')
    return re.sub(r'nvapi-[A-Za-z0-9_-]+', '[REDACTED]', text)[:800]


def _status_code(error: Exception) -> int | None:
    code = getattr(error, 'status_code', None) or getattr(getattr(error, 'response', None), 'status_code', None)
    match = re.search(r'(?:\[|HTTP\s+|status(?:\s+code)?[=: ]+)([45]\d\d)', str(error), re.I)
    return code or (int(match.group(1)) if match else None)


def _trace(model: str, source: str, seconds: float, error: Exception | None = None) -> None:
    record = {'ts': datetime.now(timezone.utc).isoformat(), 'model': model, 'model_id': MODEL_IDS[model],
              'source': source, 'seconds': round(seconds, 3), 'ok': error is None,
              'error': _safe_error(error) if error else None}
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open('a') as stream:
            stream.write(json.dumps(record) + '\n')
    except OSError:
        pass


def _extract_json(text: str) -> Any:
    text = _strip_reasoning(text)
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fenced:
        text = fenced.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise ValueError("no JSON object found in reply")
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[start:end + 1])


def _validate(obj: Any, schema: dict) -> None:
    try:
        import jsonschema
        try:
            jsonschema.validate(obj, schema)
        except jsonschema.ValidationError as error:
            raise ValueError(error.message) from None
    except ImportError:
        for key in schema.get("required", []):
            if key not in obj:
                raise ValueError(f"missing required key: {key}")


def _invoke(model: str, system: str, user: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage
    delay = 2.0
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = _client(model)
            schema = _schema_context.get()
            if schema:
                client = client.bind(response_format={'type': 'json_schema', 'json_schema': {
                    'name': 'response', 'schema': schema, 'strict': True}})
            reply = client.invoke([SystemMessage(content=system),
                                           HumanMessage(content=user)])
            content = _strip_reasoning(reply.content) if isinstance(reply.content, str) else ''
            if not content:
                raise ValueError('Model returned no final answer; empty replies are never cached')
            return content
        except LLMError:
            raise
        except Exception as e:  # rate limits, timeouts, 5xx
            last_err = e
            code = _status_code(e)
            if code and 400 <= code < 500 and code not in (408, 429):
                raise LLMError(f'{MODEL_IDS[model]} rejected request: {_safe_error(e)}') from None
            print(f"[llm] {model} attempt {attempt}/{MAX_RETRIES} failed: {_safe_error(e)}")
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
    raise LLMError(f"{model} failed after {MAX_RETRIES} attempts: {_safe_error(last_err)}")


def call_llm(model: Literal["nano", "super"], system: str, user: str,
             json_schema: Optional[dict] = None) -> dict | str:
    if model not in MODEL_IDS:
        raise ValueError(f"model must be 'nano' or 'super', got {model!r}")

    if _mode() == "fake":
        raise LLMError("LLM_MODE=fake: call_llm should not be reached. "
                       "Stub agents return fake data without calling the model.")

    started = time.monotonic()
    key = _cache_key(model, system, user, json_schema)
    cache_file = CACHE_DIR / f"{key}.json"
    if USE_CACHE and cache_file.exists():
        try:
            result = json.loads(cache_file.read_text())["result"]
            if json_schema:
                _validate(result, json_schema)
            elif not isinstance(result, str) or not result.strip():
                raise ValueError('Empty cached response')
            _trace(model, 'cache', time.monotonic() - started)
            return result
        except (ValueError, KeyError, TypeError):
            pass  # corrupt caches are regenerated, never accepted as model output

    try:
        token = _schema_context.set(json_schema)
        try:
            result = _uncached(model, system, user, json_schema)
        finally:
            _schema_context.reset(token)
    except Exception as error:
        _trace(model, 'live', time.monotonic() - started, error)
        raise
    if not json_schema and (not isinstance(result, str) or not result.strip()):
        raise LLMError('Model returned an empty final answer')
    if USE_CACHE:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=CACHE_DIR, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump({'model': MODEL_IDS[model], 'result': result}, stream)
            os.replace(temporary, cache_file)
        finally:
            Path(temporary).unlink(missing_ok=True)
    _trace(model, 'live', time.monotonic() - started)
    return result


def _uncached(model: str, system: str, user: str, json_schema: Optional[dict]):

    if json_schema:
        system_json = (system + "\n\nReturn ONLY valid JSON matching this schema, "
                       "no prose, no markdown:\n" + json.dumps(json_schema))
        raw = _invoke(model, system_json, user)
        try:
            result = _extract_json(raw)
            _validate(result, json_schema)
        except Exception as e:
            repair = (f"{user}\n\nYour previous reply was invalid: {e}\n"
                      f"Previous reply:\n{raw}\n\nReturn ONLY the corrected JSON.")
            raw = _invoke(model, system_json, repair)
            result = _extract_json(raw)
            _validate(result, json_schema)
    else:
        result = _invoke(model, system, user)

    return result


if __name__ == "__main__":
    # Smoke test: python llm.py
    print(call_llm("nano", "You are terse.", "Say hello in 3 words."))
    print(call_llm("nano", "Extract fields.", "Name: Ada, age 36",
                   json_schema={"type": "object", "required": ["name", "age"]}))
