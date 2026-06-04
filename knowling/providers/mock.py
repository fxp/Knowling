"""Offline mock provider — keeps the skeleton runnable with zero API keys.

It branches on the ``task`` hint and reads a ``meta`` kwarg (the structured
KnowledgePoint / BlockSpec the capability already has) so it never has to parse
the prompt text:

  * ``task="plan"``         → a default 3-block KnowlingSpec (text/param_sim/quiz)
  * ``task="compile_block"``→ delegates to the block's deterministic template
                              renderer in ``knowling.blocks``

Real providers ignore both ``task`` and ``meta``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .base import Completion, LLMProvider, Message


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, model: str = "mock-1", **opts: Any) -> None:
        super().__init__(model, **opts)

    def complete(
        self,
        messages: List[Message],
        *,
        task: str = "generic",
        temperature: float = 0.6,
        max_tokens: int = 4096,
        meta: Dict[str, Any] = None,
        **kwargs: Any,
    ) -> Completion:
        meta = meta or {}
        if task == "plan":
            text = json.dumps(self._plan(meta.get("kp", {})), ensure_ascii=False, indent=2)
        elif task == "compile_block":
            text = self._compile_block(meta.get("block", {}))
        else:
            text = "[mock] no handler for task=%s" % task
        # crude token estimate so cost audit has non-zero rows
        approx = max(1, len(text) // 4)
        return Completion(
            text=text,
            model=self.model,
            provider=self.name,
            prompt_tokens=approx,
            completion_tokens=approx,
            cost_usd=0.0,
        )

    # ── plan ────────────────────────────────────────────────────────
    @staticmethod
    def _plan(kp: Dict[str, Any]) -> Dict[str, Any]:
        title = kp.get("title", "知识点")
        desc = kp.get("description", "")
        objectives = kp.get("learning_objectives", [])
        return {
            "knowledge_point_id": kp.get("id", "kp.unknown"),
            "pedagogy": {
                "hook": f"为什么「{title}」会这样？先动手试试。",
                "central_phenomenon": f"调整参数时，{title} 的结果如何随之变化。",
                "misconceptions": ["以为结果与输入无关", "把相关当成因果"],
                "aha_moment": f"亲眼看到改变输入立刻改变了 {title} 的输出。",
            },
            "blocks": [
                {
                    "block_id": "b1-intro",
                    "type": "text",
                    "intent": "用一段话点明知识点与中心现象",
                    "content_spec": {
                        "md": f"## {title}\n\n{desc or title}\n\n"
                        + ("**学完后你能：** " + "；".join(objectives) if objectives else "")
                    },
                },
                {
                    "block_id": "b2-sim",
                    "type": "param_sim",
                    "intent": "让读者拖动滑块，观察输出随输入连续变化",
                    "content_spec": {
                        "params": [
                            {"name": "x", "label": "输入 x", "min": 0, "max": 10, "step": 0.1, "default": 2}
                        ],
                        "outputs": [
                            {"name": "y", "label": "输出 y = x²", "expr": "x * x"}
                        ],
                        "explain": "拖动 x，观察 y 如何变化——这就是该知识点的核心现象。",
                    },
                    "interaction_spec": {
                        "controls": [{"kind": "slider", "param": "x"}],
                        "invariants": ["拖动滑块后输出数值立即更新"],
                        "guided_steps": ["把 x 拖到最小", "再拖到最大", "观察 y 的变化速度"],
                    },
                },
                {
                    "block_id": "b3-quiz",
                    "type": "quiz",
                    "intent": "检验是否理解中心现象",
                    "content_spec": {
                        "question": f"关于「{title}」，下列哪项正确？",
                        "options": ["输出随输入变化", "输出恒定不变", "二者无关", "无法判断"],
                        "answer": 0,
                        "explain": "输出确实随输入而变化——这正是本知识点的中心现象。",
                    },
                    "interaction_spec": {
                        "controls": [{"kind": "radio"}],
                        "invariants": ["选错显示解释", "选对标记正确"],
                    },
                },
            ],
            "render_target": "html",
            "version": 1,
        }

    # ── compile ─────────────────────────────────────────────────────
    @staticmethod
    def _compile_block(block: Dict[str, Any]) -> str:
        # lazy import to avoid import cycle (blocks → schema only)
        from ..blocks import render_block_template

        return render_block_template(block)
