"""Author a Manim scene with a visual-review loop (optional [manim]).

LLMs write Manim scripts that *run* but often place Text labels poorly —
overlapping, off-frame, or detached from what they annotate. So generation is a
loop, not a one-shot:

    generate script → render → (render error? repair with traceback)
                    → extract key frames → VLM reviews text placement
                    → issues? repair the script with the visual feedback → re-render

We keep the best-scoring candidate across rounds. Mirrors Knowling's three-dim
QA, specialized for rendered animation.
"""

from __future__ import annotations

import base64
import re
from typing import Any, Dict, List, Optional

from ..providers.base import LLMProvider
from ._extract import extract_json
from . import manim_render

GEN_SYSTEM = (
    "你是 ManimCommunity(v0.19) 动画工程师。只输出一段完整 Python 代码，"
    "禁止解释、禁止 markdown 代码围栏。"
)

# Visual-quality rubric — the whole point is catching text-placement problems.
REVIEW_SYSTEM = (
    "你是数学动画视觉质检员（对标 3Blue1Brown 的清晰度）。看这些关键帧，"
    "**重点检查文字/标签**：是否相互重叠、是否超出画面边界、是否遮挡或远离其所标注的图形、"
    "字号是否过大或过小、整体是否整洁清楚。"
)
REVIEW_PROMPT = (
    "审查这段数学动画的关键帧（按时间顺序）。聚焦文字位置问题。"
    '输出 JSON: {"score": 0-5, "issues": [具体问题, 中文], '
    '"fixes": [针对 Manim 脚本的可执行修改建议, 如"把 a² 标签 move_to 左上块中心"]}。'
    "score≥4 表示文字位置基本无问题。"
)

_POSITION_RULES = (
    "定位要求：所有 Text 不得重叠、不得超出画面；标签要紧贴(.next_to/.move_to)其标注的对象，"
    "区域面积标签放到该区域中心；字号适中(font_size 24~36)；给标签留白，必要时缩小图形或用 "
    "VGroup(...).arrange / .to_edge / .scale_to_fit_width(config.frame_width-1) 适配画面。"
)


def _strip_code(t: str) -> str:
    m = re.search(r"```(?:python)?\s*(.*?)```", t or "", re.S)
    return (m.group(1) if m else (t or "")).strip()


def _b64(png: bytes) -> str:
    return base64.b64encode(png).decode("ascii")


def review_frames(frames: List[bytes], vlm: LLMProvider) -> Dict[str, Any]:
    """VLM review of rendered frames → {score, issues, fixes}. Never raises."""
    if not frames or vlm.name == "mock":
        return {"score": 5.0, "issues": [], "fixes": [], "note": "no VLM / offline"}
    content: List[Dict[str, Any]] = [{"type": "text", "text": REVIEW_PROMPT}]
    for png in frames:
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/png;base64," + _b64(png)}})
    try:
        comp = vlm.complete([{"role": "system", "content": REVIEW_SYSTEM},
                             {"role": "user", "content": content}],
                            task="qa_render", temperature=0.2, max_tokens=2048)
    except Exception as e:
        return {"score": 3.0, "issues": [], "fixes": [], "note": f"vlm error: {e}"}
    data = extract_json(comp.text)
    if not isinstance(data, dict) or "score" not in data:
        return {"score": 3.0, "issues": [], "fixes": [], "note": "unparseable review"}
    return {
        "score": float(data.get("score", 0)),
        "issues": [str(x) for x in data.get("issues", [])],
        "fixes": [str(x) for x in data.get("fixes", [])],
    }


def author(
    concept_prompt: str,
    scene: str,
    text_provider: LLMProvider,
    vlm_provider: LLMProvider,
    *,
    max_rounds: int = 3,
    accept: float = 4.0,
    quality: str = "medium",
    emit=None,
) -> Optional[Dict[str, Any]]:
    """Generate + render + visually review a Manim scene, repairing across rounds.

    Returns the best candidate: {script, scene, video(data-uri), review, rounds}
    or None if nothing ever rendered. ``concept_prompt`` should describe the
    animation; the class name is pinned to ``scene``."""
    def log(msg):
        if emit:
            emit("stage", {"stage": "manim", "status": "review", "msg": msg})

    base = [
        {"role": "system", "content": GEN_SYSTEM},
        {"role": "user", "content": (
            f"{concept_prompt}\n\n严格要求：只输出完整 python，恰好一个 Scene 子类，"
            f"类名必须是 {scene}。禁止 Tex/MathTex/Title（无 LaTeX），文字一律用 Text(...)。\n{_POSITION_RULES}\n只输出代码。"
        )},
    ]
    msgs = list(base)
    best: Optional[Dict[str, Any]] = None
    last_script = ""

    for r in range(max_rounds):
        comp = text_provider.complete(msgs, task="compile_block", temperature=0.3, max_tokens=4000)
        script = _strip_code(comp.text) or last_script
        last_script = script
        data, err = manim_render.render(script, scene, quality=quality)
        if data is None:
            log(f"round {r}: render error → repair")
            msgs = base + [{"role": "assistant", "content": script},
                           {"role": "user", "content": f"上面的代码渲染失败，错误如下，请修正后只输出完整代码：\n{err[:1200]}"}]
            continue
        frames = manim_render.extract_frames(data, 3)
        review = review_frames(frames, vlm_provider)
        cand = {"script": script, "scene": scene,
                "video": manim_render.mp4_to_data_uri(data), "review": review, "rounds": r + 1}
        if best is None or review["score"] > best["review"]["score"]:
            best = cand
        log(f"round {r}: visual score {review['score']} issues={len(review.get('issues', []))}")
        if review["score"] >= accept and not review.get("issues"):
            break
        feedback = "；".join((review.get("issues") or []) + (review.get("fixes") or [])) or "文字位置需更清晰"
        msgs = base + [
            {"role": "assistant", "content": script},
            {"role": "user", "content": (
                f"上一版动画经视觉质检发现以下**文字位置**问题：{feedback}。\n"
                f"请修改脚本修复这些问题。{_POSITION_RULES}\n保持类名 {scene}，只输出完整代码。"
            )},
        ]
    return best
