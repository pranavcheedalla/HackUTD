"""Pull a JSON value out of a model reply (handles <think> blocks, ``` fences, prose around it)."""
from __future__ import annotations

import json
import re

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)


def strip_reasoning(text: str) -> str:
    text = _THINK.sub("", text)
    # Reasoning models sometimes emit only the closing tag.
    if "</think>" in text.lower():
        text = re.split(r"</think>", text, flags=re.I)[-1]
    return text.strip()


def extract_json(text: str):
    """Return the first JSON object/array found in text. Raises ValueError if none parses."""
    if not isinstance(text, str):
        return text
    text = strip_reasoning(text)
    candidates = [m.group(1) for m in _FENCE.finditer(text)] + [text]
    decoder = json.JSONDecoder()
    for cand in candidates:
        cand = cand.strip()
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass
        for i, ch in enumerate(cand):
            if ch in "{[":
                try:
                    value, _ = decoder.raw_decode(cand[i:])
                    return value
                except json.JSONDecodeError:
                    continue
    raise ValueError(f"no valid JSON found in model reply (starts: {text[:120]!r})")
