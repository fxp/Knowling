"""Extract JSON / HTML from possibly-fenced LLM output."""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def extract_json(text: str) -> Optional[Any]:
    """Pull the first JSON object/array out of an LLM reply (handles ```fences)."""
    if not text:
        return None
    # fenced ```json ... ```
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = m.group(1) if m else text
    candidate = candidate.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # fall back: first {...} or [...] span
    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


def extract_html(text: str) -> str:
    """Pull an HTML fragment out of an LLM reply; strip code fences if present."""
    if not text:
        return ""
    m = re.search(r"```(?:html)?\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()
