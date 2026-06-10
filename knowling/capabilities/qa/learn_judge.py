"""F4 — learnability feedback (knowledge acquisition).

The ultimate test of a teaching card: after a learner *reads only the card*,
have they actually acquired the knowledge this point requires?

We simulate a learner who already masters every prerequisite (``kp.prerequisites``)
but has **not** yet learned this point. They may use *only* what the card states or
lets them derive — outside/common knowledge does not count. For each learning
objective the judge decides whether the card alone makes the needed knowledge
acquirable (``covered`` / ``partial`` / ``missing``) and what is missing.

This is distinct from the pedagogy dimension (which scores focus / accuracy /
explorable value): here we score *sufficiency of transmission*. Runs last, after
render + interact + pedagogy pass (design §6.1 ordering). Strong LLM judge;
offline → lenient heuristic over the artifact text + spec.
"""

from __future__ import annotations

import html as _html
import re
from typing import Any, List, Optional

from ...providers.base import LLMProvider
from .._extract import complete_json
from .types import DimensionFeedback, QAConfig

SYSTEM = (
    "你扮演一名学习者：已经牢固掌握该知识点的全部前置知识，但尚未学过这个知识点本身。"
    "你只能依据下面这张教学卡的内容来学习——卡片没讲、也无法由卡片内容推导出的东西，"
    "即使是常识也不算你学会了。请据此评估这张卡能否真正把所需知识传授给你。"
)

PROMPT = """知识点：{title}
一句话界定：{description}
你已掌握的前置知识：{prerequisites}

下面是教学卡的全部可见内容（你只能用这些来学习）：
\"\"\"
{text}
\"\"\"

请逐条判断：一个具备上述前置知识的学习者，**仅凭这张卡的内容**，能否获得达成下列每条学习目标所需的知识？
学习目标：
{objectives}

判定标准（严格）：
- covered：卡片把所需知识讲清楚了，或给出了足以让人当场推导/归纳出来的内容（含可交互演示能让人观察到的规律）。
- partial：卡片沾了边但关键步骤/定义/条件缺失，学习者得靠卡片之外的知识才能补全。
- missing：卡片基本没有提供达成该目标所需的知识。
注意：不要因为你自己本来就懂这个知识点而判 covered——只看卡片是否真的把它讲了出来。

输出 JSON：
{{"objectives": [{{"objective": str, "verdict": "covered|partial|missing", "evidence": str, "gap": str}}],
  "score": 0-5, "suggestions": [str]}}
score 反映整体可学会程度：目标全部 covered≈5；有 partial 适当扣分；有 missing 大幅扣分。
suggestions 给可执行的补充建议（应补什么内容/演示，使缺失目标变为 covered）。"""


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
    if provider is not None and provider.name != "mock":
        fb = _assess_llm(artifact_html, spec, kp, provider, cfg)
        if fb is not None:
            fb.passed = fb.score >= cfg.learn_threshold
            return fb
    return _assess_heuristic(artifact_html, kp, cfg)


def _assess_llm(artifact_html, spec, kp, provider, cfg: QAConfig) -> Optional[DimensionFeedback]:
    objs = (kp.learning_objectives if kp else []) or []
    if not objs:
        # nothing concrete to acquire — fall back to the heuristic's lenient view.
        return None
    user = PROMPT.format(
        title=getattr(kp, "title", getattr(spec, "knowledge_point_id", "")),
        description=getattr(kp, "description", "") or "（未提供）",
        prerequisites="；".join(kp.prerequisites) if getattr(kp, "prerequisites", None) else "（默认已具备一切前置知识）",
        objectives="\n".join(f"- {o}" for o in objs),
        text=_visible_text(artifact_html)[:4000],
    )
    try:
        data, _comp = complete_json(
            provider,
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            task="qa_learnability", temperature=0.2, max_tokens=3000,
        )
    except Exception:
        return None
    if not isinstance(data, dict) or "score" not in data:
        return None
    suggestions = list(data.get("suggestions", []))
    # surface the specific gaps for non-covered objectives so a re-compile can fix them.
    for o in data.get("objectives", []) or []:
        if isinstance(o, dict) and o.get("verdict") in ("partial", "missing") and o.get("gap"):
            suggestions.append(f"学习目标「{o.get('objective', '')}」缺：{o['gap']}")
    return DimensionFeedback(
        stage="learn",
        score=float(data.get("score", 0)),
        suggestions=suggestions,
        description="LLM learnability review (learner can acquire the knowledge from the card alone)",
    )


def _assess_heuristic(artifact_html, kp, cfg: QAConfig) -> DimensionFeedback:
    """Lenient offline proxy: does the card text actually carry content for each
    objective? We can't truly simulate learning without an LLM, so we degrade
    gracefully (objective token coverage + enough substance), matching the rest of
    the offline QA path which stays green on templated/mock cards."""
    text = _visible_text(artifact_html)
    score = 5.0
    suggestions: List[str] = []

    objs = (kp.learning_objectives if kp else []) or []
    for obj in objs:
        toks = [t for t in re.split(r"[，,。、；;\s/]+", obj) if len(t) >= 2]
        hit = sum(1 for t in toks if t in text)
        cov = hit / len(toks) if toks else 1.0
        if cov < 0.3:
            score -= 1.0
            suggestions.append(f"卡片内容几乎未触及学习目标，学习者无法获得：{obj}")
        elif cov < 0.6:
            score -= 0.5
            suggestions.append(f"卡片对该目标讲解不足，学习者可能学不全：{obj}")

    # a card with almost no prose can't transmit knowledge regardless of coverage.
    if len(text) < 80:
        score -= 1.0
        suggestions.append("可见正文过少，不足以让学习者真正获得知识")

    score = max(0.0, min(5.0, score))
    return DimensionFeedback(
        stage="learn",
        score=score,
        suggestions=suggestions,
        passed=score >= cfg.learn_threshold,
        description="heuristic learnability check",
    )
