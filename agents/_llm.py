"""LLM access for Person 4's agents.

Uses the shared `llm.call_llm` (Hemant's wrapper) if it is importable; otherwise
falls back to a self-contained ChatNVIDIA client with the SAME signature:

    call_llm(model: "nano"|"super", system: str, user: str, json_schema: dict|None) -> dict|str

So these agents work standalone today and switch to the shared wrapper after merge
with no code changes. Set P4_FORCE_LOCAL_LLM=1 to always use the local client.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CACHE_DIR = _ROOT / "dev" / "p4" / ".cache" / "llm"

MODEL_IDS = {
    "super": os.environ.get("NEMOTRON_SUPER", "nvidia/nemotron-3-super-120b-a12b"),
    "nano": os.environ.get("NEMOTRON_NANO", "nvidia/nemotron-3-nano-30b-a3b"),
}


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


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning blocks some Nemotron models emit."""
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


def _local_call_llm(model: str, system: str, user: str, json_schema: dict | None = None):
    _load_dotenv()
    if json_schema is not None:
        system = (
            system
            + "\n\nRespond with ONLY a JSON object (no prose, no markdown) matching this JSON schema:\n"
            + json.dumps(json_schema)
        )

    key = hashlib.sha256(
        json.dumps([model, MODEL_IDS[model], system, user], sort_keys=True).encode()
    ).hexdigest()
    cache_file = _CACHE_DIR / f"{key}.json"
    if cache_file.is_file():
        text = json.loads(cache_file.read_text())["text"]
    else:
        text = _invoke(model, system, user)
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"model": model, "text": text}))

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
        return extract_json(repaired)


def _invoke(model: str, system: str, user: str) -> str:
    if not os.environ.get("NVIDIA_API_KEY"):
        raise RuntimeError("NVIDIA_API_KEY not set (put it in .env or export it)")
    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    llm = ChatNVIDIA(model=MODEL_IDS[model], temperature=0.2, max_completion_tokens=8192)
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            resp = llm.invoke([("system", system), ("user", user)])
            return resp.content if isinstance(resp.content, str) else str(resp.content)
        except Exception as e:  # rate limits, timeouts
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"LLM call failed after retries: {last_err}")


call_llm = _local_call_llm
if os.environ.get("P4_FORCE_LOCAL_LLM") != "1":
    try:
        from llm import call_llm  # type: ignore  # noqa: F811  (shared wrapper, after merge)
    except ImportError:
        pass
