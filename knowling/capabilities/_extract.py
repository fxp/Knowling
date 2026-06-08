"""Extract JSON / HTML from possibly-fenced LLM output."""

from __future__ import annotations

import json
import re
from typing import Any, List, Optional, Tuple


def complete_json(
    provider,
    messages: List[dict],
    *,
    task: str = "generic",
    retries: int = 2,
    **kw: Any,
) -> Tuple[Optional[Any], Any]:
    """``provider.complete`` + ``extract_json`` with retry-on-unparseable.

    Reasoning models (e.g. GLM-5) intermittently emit prose/thinking that starves
    or breaks the JSON. On a parse miss we retry with thinking off and a strict
    "JSON only" nudge. Returns ``(data, last_completion)``; ``data`` is ``None``
    if every attempt fails. ``thinking`` defaults to ``"disabled"``."""
    kw.setdefault("thinking", "disabled")
    last = None
    msgs = list(messages)
    for attempt in range(retries + 1):
        try:
            last = provider.complete(msgs, task=task, **kw)
        except Exception:
            # transient provider/network error (e.g. connection reset) — retry,
            # but let the final attempt's exception propagate.
            if attempt == retries:
                raise
            continue
        data = extract_json(last.text)
        if data is not None:
            return data, last
        msgs = list(messages) + [{
            "role": "user",
            "content": "你上次的回复无法被解析为 JSON。请直接输出一个合法的 JSON，"
                       "不要输出任何思考过程、解释或多余文本。",
        }]
    return None, last


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
    # fall back A: first {...} or [...] span (greedy)
    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                break

    # fall back B: balanced-brace scan from first '{' (handles trailing prose)
    start = candidate.find("{")
    if start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(candidate)):
            ch = candidate[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(candidate[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def extract_html(text: str) -> str:
    """Pull an HTML fragment out of an LLM reply; strip code fences if present."""
    if not text:
        return ""
    m = re.search(r"```(?:html)?\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()
