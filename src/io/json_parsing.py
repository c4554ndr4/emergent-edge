from __future__ import annotations

import json
import re
from typing import Any


def parse_json_from_text(raw: str) -> Any:
    """Parse JSON from raw LLM text, including fenced blocks or surrounding prose."""
    text = raw.strip()
    if not text:
        raise ValueError("empty response")

    # Fast path
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try fenced code block
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    for chunk in fenced:
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue

    # Scan for first valid JSON object/array
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch not in "[{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
            return obj
        except json.JSONDecodeError:
            continue

    raise ValueError("could not parse JSON from response")
