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
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Literal, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / ".cache" / "llm"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Verify the exact IDs on build.nvidia.com and put them in .env
MODEL_IDS = {
    "nano": os.getenv("NEMOTRON_NANO_MODEL", "nvidia/nemotron-3-nano-30b-a3b"),
    "super": os.getenv("NEMOTRON_SUPER_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
}
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "4"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8192"))
USE_CACHE = os.getenv("LLM_CACHE", "1") != "0"

_clients: dict[str, Any] = {}


class LLMError(RuntimeError):
    pass


def _mode() -> str:
    return os.getenv("LLM_MODE", "real").lower()


def _client(model: str):
    if model not in _clients:
        from langchain_nvidia_ai_endpoints import ChatNVIDIA
        key = os.getenv("NVIDIA_API_KEY")
        if not key:
            raise LLMError("NVIDIA_API_KEY missing. Put it in .env or set LLM_MODE=fake.")
        kwargs = dict(model=MODEL_IDS[model], api_key=key,
                      temperature=TEMPERATURE, max_completion_tokens=MAX_TOKENS)
        base_url = os.getenv("NVIDIA_BASE_URL")  # set for local vLLM/Ollama, else hosted NIM
        if base_url:
            kwargs["base_url"] = base_url
        _clients[model] = ChatNVIDIA(**kwargs)
    return _clients[model]


def _cache_key(model: str, system: str, user: str, schema: Optional[dict]) -> str:
    blob = json.dumps([MODEL_IDS[model], system, user, schema], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def _strip_reasoning(text: str) -> str:
    # Nemotron reasoning models may emit <think>...</think> before the answer
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


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
        jsonschema.validate(obj, schema)
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
            reply = _client(model).invoke([SystemMessage(content=system),
                                           HumanMessage(content=user)])
            return _strip_reasoning(reply.content)
        except LLMError:
            raise
        except Exception as e:  # rate limits, timeouts, 5xx
            last_err = e
            print(f"[llm] {model} attempt {attempt}/{MAX_RETRIES} failed: {e}")
            time.sleep(delay)
            delay *= 2
    raise LLMError(f"{model} failed after {MAX_RETRIES} attempts: {last_err}")


def call_llm(model: Literal["nano", "super"], system: str, user: str,
             json_schema: Optional[dict] = None) -> dict | str:
    if model not in MODEL_IDS:
        raise ValueError(f"model must be 'nano' or 'super', got {model!r}")

    if _mode() == "fake":
        raise LLMError("LLM_MODE=fake: call_llm should not be reached. "
                       "Stub agents return fake data without calling the model.")

    key = _cache_key(model, system, user, json_schema)
    cache_file = CACHE_DIR / f"{key}.json"
    if USE_CACHE and cache_file.exists():
        return json.loads(cache_file.read_text())["result"]

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

    if USE_CACHE:
        cache_file.write_text(json.dumps({"model": MODEL_IDS[model], "result": result}))
    return result


if __name__ == "__main__":
    # Smoke test: python llm.py
    print(call_llm("nano", "You are terse.", "Say hello in 3 words."))
    print(call_llm("nano", "Extract fields.", "Name: Ada, age 36",
                   json_schema={"type": "object", "required": ["name", "age"]}))
