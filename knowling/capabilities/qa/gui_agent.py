"""F2 — interaction feedback (design §6.1).

Validates each block's ``qa_assertions`` (the ``interaction_spec.invariants``,
design §7). Static checks run against the rendered HTML and are reliable
structural signals; with Playwright the same assertions gate a live no-JS-error
load. A model-driven GUI agent (semantic ``gui_hint`` checks) is a P2 follow-up.

Only runs after render passes (design §6.1 ordering).
"""

from __future__ import annotations

from typing import List

from ... import blocks as block_registry
from ...providers.base import LLMProvider
from ...sandbox.base import RenderResult
from .types import DimensionFeedback, QAConfig


def test(
    render: RenderResult,
    spec_blocks: List[dict],
    provider: LLMProvider,
    cfg: QAConfig,
) -> DimensionFeedback:
    html = render.html
    total = 0
    failed: List[dict] = []
    failed_block_ids: List[str] = []

    for block in spec_blocks:
        for assertion in block_registry.qa_assertions(block):
            total += 1
            check = assertion.get("check")
            ok = True
            try:
                ok = bool(check(html)) if check else True
            except Exception:
                ok = False
            if not ok:
                failed.append(assertion)
                bid = block.get("block_id", "")
                if bid and bid not in failed_block_ids:
                    failed_block_ids.append(bid)

    # live load must be error-free if we have a real browser
    if render.backend == "playwright" and render.console_errors:
        total = max(total, 1)
        failed.append({"id": "runtime", "description": "运行时报错"})

    if total == 0:
        # no interactive invariants to check (e.g. all-text component)
        return DimensionFeedback(stage="interact", score=5.0, passed=True,
                                 description="no interaction invariants")

    passed_count = total - len(failed)
    score = 5.0 * passed_count / total
    suggestions = [f"未满足交互断言: {a.get('description', a.get('id'))}" for a in failed]
    return DimensionFeedback(
        stage="interact",
        score=score,
        suggestions=suggestions,
        passed=score >= cfg.interact_threshold,
        description=f"{passed_count}/{total} 交互断言通过",
        failed_block_ids=failed_block_ids,
    )
