"""Fidelity guard — keep a card on its knowledge point (anti-drift).

Refinement is where drift is most likely: "和导数是什么关系？" can quietly turn
a chain-rule card into a derivatives card. This module checks whether a spec is
still *about* its KnowledgePoint and reports drift, so the engine can re-anchor.

Real LLM: judges topic fidelity. Offline: a token-coverage heuristic over the
spec's own text — does the knowledge point's vocabulary still dominate the card?
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Optional

from ..providers.base import LLMProvider
from ..schema import KnowlingSpec
from ._extract import extract_json

SYSTEM = "你是教学内容审核员。判断一张学习卡是否仍然聚焦于指定知识点（没有跑题到别的主题）。"

PROMPT = """知识点: {title} — {description}
学习目标: {objectives}

这张学习卡的全部文本内容:
\"\"\"
{text}
\"\"\"

判断: 这张卡是否**始终在讲解该知识点本身**, 而不是跑题成讲另一个主题?
(围绕本知识点说明它与相邻知识点的"关系"是允许的; 但主体若变成讲那个相邻知识点就算跑题。)
输出 JSON: {{"on_topic": true/false, "score": 0-5, "reason": "一句话"}}。"""


@dataclass
class Fidelity:
    ok: bool
    score: float
    reason: str = ""

    def to_dict(self):
        return {"on_topic": self.ok, "score": round(self.score, 2), "reason": self.reason}


_STOP = {"的", "了", "和", "与", "是", "在", "对", "为", "其", "这", "那", "如何", "什么", "一个", "可以"}


def _tokens(s: str) -> List[str]:
    out = []
    for t in re.split(r"[\s，,。、.;；:：!！?？()（）\"'\[\]【】<>/=+\-*]+", s or ""):
        t = t.strip()
        if len(t) >= 2 and t not in _STOP:
            out.append(t.lower())
    return out


def spec_text(spec: KnowlingSpec) -> str:
    """Concatenate the human-facing text carried by a spec (no rendering)."""
    parts: List[str] = []
    p = spec.pedagogy
    if p:
        parts += [p.hook, p.central_phenomenon, p.aha_moment, *p.misconceptions]
    for b in spec.blocks:
        parts.append(b.intent or "")
        cs = b.content_spec or {}
        for key in ("md", "question", "explain", "summary", "expanded_md", "title", "caption"):
            v = cs.get(key)
            if isinstance(v, str):
                parts.append(v)
        for arr_key, fields in (("options", None), ("steps", ("state", "explain")),
                                ("questions", ("prompt", "explain")), ("events", ("label", "detail"))):
            for item in cs.get(arr_key, []) or []:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    for f in (fields or item.keys()):
                        if isinstance(item.get(f), str):
                            parts.append(item[f])
    return "\n".join(x for x in parts if x)


def assess(
    spec: KnowlingSpec,
    kp,
    provider: LLMProvider,
    threshold: float = 3.0,
) -> Fidelity:
    text = spec_text(spec)
    if provider.name != "mock":
        fb = _assess_llm(text, kp, provider, threshold)
        if fb is not None:
            return fb
    return _assess_heuristic(text, kp, threshold)


def _assess_llm(text: str, kp, provider: LLMProvider, threshold: float) -> Optional[Fidelity]:
    user = PROMPT.format(
        title=getattr(kp, "title", ""),
        description=getattr(kp, "description", "") or "",
        objectives="；".join(getattr(kp, "learning_objectives", []) or []) or "（未指定）",
        text=text[:4000],
    )
    try:
        comp = provider.complete(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            task="fidelity", temperature=0.1, max_tokens=1500, thinking="disabled",
        )
    except Exception:
        return None
    data = extract_json(comp.text)
    if not isinstance(data, dict) or "score" not in data:
        return None
    score = float(data.get("score", 0))
    ok = bool(data.get("on_topic", score >= threshold)) and score >= threshold
    return Fidelity(ok=ok, score=score, reason=str(data.get("reason", "")))


def _assess_heuristic(text: str, kp, threshold: float) -> Fidelity:
    """Topic-coverage heuristic: the KP's title vocabulary should still appear."""
    title_terms = set(_tokens(getattr(kp, "title", "")))
    if not title_terms:
        return Fidelity(ok=True, score=5.0, reason="无标题可比对")
    body = (text or "").lower()
    hit = sum(1 for t in title_terms if t in body)
    coverage = hit / len(title_terms)
    score = round(min(5.0, coverage * 5.0 + (1.0 if hit else 0.0)), 2)
    ok = score >= threshold
    reason = ("聚焦良好" if ok else
              f"知识点核心词在内容中覆盖不足({hit}/{len(title_terms)})，可能跑题")
    return Fidelity(ok=ok, score=score, reason=reason)
