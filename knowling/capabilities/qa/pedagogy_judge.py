"""F3 — pedagogy feedback (design §6.1, §10.3).

Anchored on Explorable Explanations: factual accuracy, guides attention to the
central phenomenon, clears misconceptions, real explorable value, meets
objectives. Strong LLM judge; offline → heuristic over the artifact text + spec.

Only runs after render + interact pass (design §6.1 ordering).
"""

from __future__ import annotations

import html as _html
import re
from typing import Any, List, Optional

from ...providers.base import LLMProvider
from .._extract import extract_json
from .types import DimensionFeedback, QAConfig

SYSTEM = "作为教学质量评审，锚定 Explorable Explanations 准则，对学习组件打分(0-5)并给可执行建议。"

PROMPT = """对该学习组件打分(0-5)并给出可执行建议。锚定 Explorable Explanations 准则:
- 事实是否准确(对照依据材料, 标出任何幻觉)
- 是否把读者注意力引导到中心现象: {central_phenomenon}
- 是否澄清了这些误解: {misconceptions}
- 可交互元素是否有真实探索价值(改变输入会改变可观察结果)
- 是否达成学习目标: {objectives}

学习组件可见文本:
\"\"\"
{text}
\"\"\"

输出 JSON: {{"score": 0-5, "suggestions": [str]}}。"""


def _visible_text(html: str) -> str:
    txt = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    txt = re.sub(r"<style[\s\S]*?</style>", " ", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = _html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def assess(
    artifact_html: str,
    spec,
    kp,
    grounding: Optional[List[Any]],
    provider: LLMProvider,
    cfg: QAConfig,
) -> DimensionFeedback:
    if provider.name != "mock":
        fb = _assess_llm(artifact_html, spec, kp, provider)
        if fb is not None:
            fb.passed = fb.score >= cfg.pedagogy_threshold
            return fb
    return _assess_heuristic(artifact_html, spec, kp, cfg)


def _assess_llm(artifact_html, spec, kp, provider) -> Optional[DimensionFeedback]:
    ped = spec.pedagogy
    user = PROMPT.format(
        central_phenomenon=ped.central_phenomenon if ped else "",
        misconceptions="；".join(ped.misconceptions) if ped else "",
        objectives="；".join(kp.learning_objectives) if kp else "",
        text=_visible_text(artifact_html)[:4000],
    )
    try:
        comp = provider.complete(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            task="qa_pedagogy", temperature=0.2, max_tokens=800,
        )
    except Exception:
        return None
    data = extract_json(comp.text)
    if not isinstance(data, dict) or "score" not in data:
        return None
    return DimensionFeedback(
        stage="pedagogy",
        score=float(data.get("score", 0)),
        suggestions=list(data.get("suggestions", [])),
        description="LLM pedagogy review",
    )


def _assess_heuristic(artifact_html, spec, kp, cfg: QAConfig) -> DimensionFeedback:
    text = _visible_text(artifact_html)
    score = 5.0
    suggestions: List[str] = []
    ped = spec.pedagogy

    def _has_explorable() -> bool:
        return any(b.type in ("param_sim", "interactive_demo", "step_through")
                   for b in spec.blocks)

    if not _has_explorable():
        score -= 1.5
        suggestions.append("缺少可探索块(param_sim/step_through)，探索价值不足")

    # objectives coverage (token overlap heuristic)
    objs = (kp.learning_objectives if kp else []) or []
    for obj in objs:
        toks = [t for t in re.split(r"[，,。\s]+", obj) if len(t) >= 2]
        hit = sum(1 for t in toks if t in text)
        if toks and hit / len(toks) < 0.3:
            score -= 0.5
            suggestions.append(f"未充分覆盖学习目标: {obj}")

    if ped and ped.central_phenomenon:
        key = [t for t in re.split(r"[，,。\s的]+", ped.central_phenomenon) if len(t) >= 2]
        if key and not any(t in text for t in key):
            score -= 0.5
            suggestions.append("正文未明确引导到中心现象")

    if len(text) < 40:
        score -= 1.0
        suggestions.append("文本过少，叙述引导不足")

    score = max(0.0, min(5.0, score))
    return DimensionFeedback(
        stage="pedagogy",
        score=score,
        suggestions=suggestions,
        passed=score >= cfg.pedagogy_threshold,
        description="heuristic pedagogy check",
    )
