"""Nemotron access for Person 4's agents.

    call_llm(model: "nano"|"super", system: str, user: str, json_schema: dict|None) -> dict|str

Backend, chosen at call time:
  1. the shared `llm.call_llm` (Hemant's wrapper) if it is importable, else
  2. the built-in ChatNVIDIA client below (Nemotron 3 Super / Nano on build.nvidia.com).
Set P4_FORCE_LOCAL_LLM=1 to always use the built-in client.

Every call, whichever backend, is appended to runs/nemotron_trace.jsonl
(agent, module, model id, latency, cache hit, Nemotron's reasoning) so the dashboard
can show which Nemotron model did what. Agents label their calls with `agent(...)`.
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CACHE_DIR = _ROOT / "dev" / "p4" / ".cache" / "llm"
TRACE_PATH = Path(os.environ.get("P4_TRACE_PATH", _ROOT / "runs" / "nemotron_trace.jsonl"))

MODEL_IDS = {
    "super": os.environ.get("NEMOTRON_SUPER", "nvidia/nemotron-3-super-120b-a12b"),
    "nano": os.environ.get("NEMOTRON_NANO", "nvidia/nemotron-3-nano-30b-a3b"),
}
# Nemotron 3 reasoning mode (chat_template_kwargs.enable_thinking). On by default: the
# reasoning goes to a separate channel, so the answer stays clean and we log the reasoning.
THINKING = os.environ.get("NEMOTRON_THINKING", "1") != "0"
MAX_TOKENS = int(os.environ.get("NEMOTRON_MAX_TOKENS", "16384"))  # reasoning + code must fit

_agent = contextvars.ContextVar("p4_agent", default=("unknown", None))
_last_reasoning = contextvars.ContextVar("p4_last_reasoning", default="")


@contextlib.contextmanager
def agent(name: str, module_id: str | None = None):
    """Label Nemotron calls made inside this block (shows up in the trace)."""
    token = _agent.set((name, module_id))
    try:
        yield
    finally:
        _agent.reset(token)


def last_reasoning() -> str:
    """Nemotron's reasoning text from the most recent built-in-client call ('' if none)."""
    return _last_reasoning.get()


# ----------------------------------------------------------------------------- public entry
def call_llm(model: str, system: str, user: str, json_schema: dict | None = None):
    backend, backend_name = _backend()
    _last_reasoning.set("")
    start = time.time()
    error = None
    try:
        return backend(model, system, user, json_schema)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        _trace(model, backend_name, time.time() - start, error)


def _backend():
    if os.environ.get("P4_FORCE_LOCAL_LLM") != "1":
        try:
            from llm import call_llm as shared  # type: ignore
            return shared, "shared llm.call_llm"
        except ImportError:
            pass
    return _local_call_llm, "p4 ChatNVIDIA"


def _trace(model: str, backend_name: str, seconds: float, error: str | None) -> None:
    name, module_id = _agent.get()
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agent": name,
        "module_id": module_id,
        "model": model,
        "model_id": MODEL_IDS.get(model, model),
        "backend": backend_name,
        "thinking": THINKING,
        "seconds": round(seconds, 2),
        "cached": _cache_hit.get(),
        "reasoning": _last_reasoning.get()[:4000],
        "error": error,
    }
    _cache_hit.set(None)
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass  # tracing must never break an agent


_cache_hit = contextvars.ContextVar("p4_cache_hit", default=None)


# ----------------------------------------------------------------------------- parsing helpers
def strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning blocks if they leak into the content."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "</think>" in text:  # opening tag missing
        text = text.split("</think>", 1)[1]
    return text.strip()


def extract_json(text: str) -> dict:
    text = strip_thinking(text)
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])


# ----------------------------------------------------------------------------- built-in client
def _load_dotenv() -> None:
    """Minimal .env loader (no python-dotenv dependency)."""
    for p in (_ROOT / ".env", Path.cwd() / ".env"):
        if p.is_file():
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _local_call_llm(model: str, system: str, user: str, json_schema: dict | None = None):
    _load_dotenv()
    if json_schema is not None:
        system = (
            system
            + "\n\nRespond with ONLY a JSON object (no prose, no markdown) matching this JSON schema:\n"
            + json.dumps(json_schema)
        )

    key = hashlib.sha256(
        json.dumps([model, MODEL_IDS[model], THINKING, system, user], sort_keys=True).encode()
    ).hexdigest()
    cache_file = _CACHE_DIR / f"{key}.json"
    if cache_file.is_file():
        cached = json.loads(cache_file.read_text())
        text, reasoning = cached["text"], cached.get("reasoning", "")
        _cache_hit.set(True)
    else:
        text, reasoning = _invoke(model, system, user)
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"model": MODEL_IDS[model], "text": text, "reasoning": reasoning}))
        _cache_hit.set(False)
    _last_reasoning.set(reasoning)

    if json_schema is None:
        return strip_thinking(text)
    try:
        return extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        # one repair retry (different prompt => different cache key)
        repaired = _local_call_llm(
            model,
            "You fix broken JSON. Output ONLY the corrected JSON object.",
            f"Error: {e}\n\nBroken output:\n{text}",
            None,
        )
        _last_reasoning.set(reasoning)
        return extract_json(repaired)


def _invoke(model: str, system: str, user: str) -> tuple[str, str]:
    if not os.environ.get("NVIDIA_API_KEY"):
        raise RuntimeError("NVIDIA_API_KEY not set (put it in .env or export it)")
    import warnings

    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        llm = ChatNVIDIA(model=MODEL_IDS[model], temperature=0.2, max_completion_tokens=MAX_TOKENS)
        runnable = llm.with_thinking_mode(enabled=THINKING)
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                resp = runnable.invoke([("system", system), ("user", user)])
                content = resp.content if isinstance(resp.content, str) else str(resp.content)
                reasoning = (resp.additional_kwargs or {}).get("reasoning_content") or ""
                if not reasoning:
                    m = re.search(r"<think>(.*?)</think>", content, flags=re.DOTALL)
                    reasoning = m.group(1).strip() if m else ""
                return content, reasoning
            except Exception as e:  # rate limits, timeouts
                last_err = e
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Nemotron call failed after retries ({MODEL_IDS[model]}): {last_err}")
