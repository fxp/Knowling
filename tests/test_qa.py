"""P1 QA-loop tests (offline, static sandbox)."""

import pytest

from knowling.assembler import assemble_html
from knowling.blocks import qa_assertions, render_block_template
from knowling.capabilities.qa import QAConfig
from knowling.capabilities.qa import gui_agent, learn_judge, render_vlm
from knowling.capabilities.qa.loop import (
    consecutive_render_failures,
    select_best,
)
from knowling.capabilities.qa.types import DimensionFeedback, StepFeedback
from knowling.providers import get_provider
from knowling.sandbox import StaticSandbox, get_sandbox
from knowling.schema import BlockSpec, KnowledgePoint, KnowlingSpec


def _spec_blocks():
    return [
        BlockSpec(block_id="b1", type="text", content_spec={"md": "# Hi"}),
        BlockSpec(
            block_id="b2", type="param_sim",
            content_spec={"params": [{"name": "x", "min": 0, "max": 5, "default": 1}],
                          "outputs": [{"name": "y", "label": "y", "expr": "x*x"}]},
        ),
        BlockSpec(
            block_id="b3", type="quiz",
            content_spec={"question": "Q", "options": ["a", "b"], "answer": 1, "explain": "ok"},
        ),
    ]


def _render(spec):
    frags = [render_block_template(b.to_dict()) for b in spec.blocks]
    html = assemble_html(spec, frags, "T")
    return get_sandbox("static").render_and_screenshot(html)


# ── assertions / scope ────────────────────────────────────────────


def test_quiz_assertions_pass_on_template():
    spec = KnowlingSpec(knowledge_point_id="k", blocks=_spec_blocks())
    render = _render(spec)
    fb = gui_agent.test(render, [b.to_dict() for b in spec.blocks], get_provider("mock", quiet=True), QAConfig())
    assert fb.passed and fb.score == 5.0
    assert fb.failed_block_ids == []


def test_assertions_detect_broken_quiz():
    # a quiz fragment missing its feedback wiring should fail interaction
    broken = '<section class="kl-block kl-quiz" data-block-id="bX"><p>Q</p></section>'
    spec = KnowlingSpec(knowledge_point_id="k", blocks=[
        BlockSpec(block_id="bX", type="quiz",
                  content_spec={"question": "Q", "options": ["a", "b"], "answer": 0})])
    html = assemble_html(spec, [broken], "T")
    render = get_sandbox("static").render_and_screenshot(html)
    fb = gui_agent.test(render, [b.to_dict() for b in spec.blocks], get_provider("mock", quiet=True), QAConfig())
    assert not fb.passed
    assert "bX" in fb.failed_block_ids


def test_render_heuristic_flags_missing_block():
    spec = KnowlingSpec(knowledge_point_id="k", blocks=_spec_blocks())
    # assemble only first two blocks → b3 missing
    frags = [render_block_template(b.to_dict()) for b in spec.blocks[:2]]
    html = assemble_html(spec, frags, "T")
    render = get_sandbox("static").render_and_screenshot(html)
    fb = render_vlm.assess(render, [b.block_id for b in spec.blocks], get_provider("mock", quiet=True), QAConfig())
    assert "b3" in fb.failed_block_ids
    assert fb.score < 5.0


# ── learnability dimension (knowledge acquisition) ────────────────


def test_learnability_heuristic_passes_when_objectives_covered():
    spec = KnowlingSpec(knowledge_point_id="链式法则", blocks=_spec_blocks())
    kp = KnowledgePoint(id="链式法则", title="链式法则",
                        learning_objectives=["理解复合函数求导", "能解释为何相乘"])
    html = ("链式法则用于复合函数求导：外层导数乘以内层导数，"
            "所以结果是两者相乘，这解释了为何相乘。" * 2)
    render = get_sandbox("static").render_and_screenshot(
        f"<main><section class='kl-block'><p>{html}</p></section></main>")
    fb = learn_judge.assess(render.html, spec, kp, None, get_provider("mock", quiet=True), QAConfig())
    assert fb.stage == "learn"
    assert fb.passed and fb.score >= 3.0


def test_learnability_heuristic_flags_uncovered_objective():
    spec = KnowlingSpec(knowledge_point_id="贝叶斯定理", blocks=_spec_blocks())
    kp = KnowledgePoint(id="贝叶斯定理", title="贝叶斯定理",
                        learning_objectives=["理解先验似然后验如何更新"])
    # generic card whose visible text never touches the objective's content
    render = get_sandbox("static").render_and_screenshot(
        "<main><section class='kl-block'><p>输入 x 输出 y 等于 x 的平方，拖动观察变化。</p></section></main>")
    fb = learn_judge.assess(render.html, spec, kp, None, get_provider("mock", quiet=True), QAConfig())
    assert fb.score < 5.0
    assert any("先验" in s or "无法获得" in s or "学不全" in s for s in fb.suggestions)


# ── select-best / backtrack (pure logic) ──────────────────────────


def _fb(render=None, interact=None, peda=None, learn=None, stage="pass"):
    return StepFeedback(
        stage=stage,
        render=DimensionFeedback("render", render) if render is not None else None,
        interact=DimensionFeedback("interact", interact) if interact is not None else None,
        pedagogy=DimensionFeedback("pedagogy", peda) if peda is not None else None,
        learn=DimensionFeedback("learn", learn) if learn is not None else None,
    )


def test_select_best_prefers_pedagogy_then_recency():
    mem = [
        ({}, _fb(5, 5, 3, stage="pedagogy")),
        ({}, _fb(5, 5, 4, stage="pedagogy")),  # higher peda
        ({}, _fb(5, 5, 4, stage="pass")),       # tie peda, later → wins
    ]
    assert select_best(mem) == 2


def test_select_best_prefers_learnability_first():
    mem = [
        ({}, _fb(5, 5, 5, learn=4, stage="learn")),
        ({}, _fb(5, 5, 3, learn=5, stage="learn")),  # higher learn beats higher peda
    ]
    assert select_best(mem) == 1


def test_consecutive_render_failures():
    mem = [
        ({}, _fb(2, stage="render")),
        ({}, _fb(5, 2, stage="interact")),
        ({}, _fb(2, stage="render")),
        ({}, _fb(2, stage="render")),
    ]
    assert consecutive_render_failures(mem) == 2


def test_static_sandbox_detects_garbage():
    r = StaticSandbox().render_and_screenshot("<x>")
    assert not r.ok
