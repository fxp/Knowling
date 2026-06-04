"""F1 — render feedback (design §6.1).

Cheap signal on visual completeness / aesthetics. With a real screenshot + VLM
(GLM-4V) it judges the image; offline it falls back to a structural heuristic
over the rendered HTML + sandbox console errors.
"""

from __future__ import annotations

import base64
from typing import List, Optional

from ...providers.base import LLMProvider
from ...sandbox.base import RenderResult
from .._extract import extract_json
from .types import DimensionFeedback, QAConfig

SYSTEM = "你是网页视觉质检员。看截图，判断视觉完整性/美观/有无错位，打分(0-5)并给改进建议。"


def assess(
    render: RenderResult,
    expected_block_ids: List[str],
    provider: LLMProvider,
    cfg: QAConfig,
) -> DimensionFeedback:
    # real path: screenshot + vision-capable provider
    if render.has_screenshot and provider.name != "mock":
        fb = _assess_vlm(render, provider)
        if fb is not None:
            fb.passed = fb.score >= cfg.render_threshold and not render.console_errors
            return fb
    # offline / fallback: heuristic over HTML + console errors
    return _assess_heuristic(render, expected_block_ids, cfg)


def _assess_vlm(render: RenderResult, provider: LLMProvider) -> Optional[DimensionFeedback]:
    try:
        with open(render.screenshot_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": [
                {"type": "text", "content": (
                    "评估这张学习组件截图。输出 JSON: "
                    "{\"score\": 0-5, \"description\": str, \"suggestions\": [str]}"
                )},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        },
    ]
    try:
        comp = provider.complete(messages, task="qa_render", temperature=0.2, max_tokens=600)
    except Exception:
        return None
    data = extract_json(comp.text) or {}
    return DimensionFeedback(
        stage="render",
        score=float(data.get("score", 0)),
        suggestions=list(data.get("suggestions", [])),
        description=str(data.get("description", "")),
    )


def _assess_heuristic(
    render: RenderResult, expected_block_ids: List[str], cfg: QAConfig
) -> DimensionFeedback:
    html = render.html
    score = 5.0
    suggestions: List[str] = []
    if not render.ok:
        score -= 2.0
        suggestions.append("沙箱渲染报告结构异常")
    for err in render.console_errors:
        score -= 1.0
        suggestions.append(f"修复运行时错误: {err[:80]}")
    if "<style" not in html:
        score -= 1.0
        suggestions.append("缺少样式，外观可能简陋")
    missing = [b for b in expected_block_ids if b and f'data-block-id="{b}"' not in html]
    if missing:
        score -= 1.0 * len(missing)
        suggestions.append(f"缺少块: {', '.join(missing)}")
    score = max(0.0, min(5.0, score))
    return DimensionFeedback(
        stage="render",
        score=score,
        suggestions=suggestions,
        passed=score >= cfg.render_threshold,
        description="heuristic render check (no browser screenshot)",
        failed_block_ids=missing,
    )
