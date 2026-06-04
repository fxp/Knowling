"""P1 QA-loop tests (offline, static sandbox)."""

import pytest

from knowling.assembler import assemble_html
from knowling.blocks import qa_assertions, render_block_template
from knowling.capabilities.qa import QAConfig
from knowling.capabilities.qa import gui_agent, render_vlm
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


# ── select-best / backtrack (pure logic) ──────────────────────────


def _fb(render=None, interact=None, peda=None, stage="pass"):
    return StepFeedback(
        stage=stage,
        render=DimensionFeedback("render", render) if render is not None else None,
        interact=DimensionFeedback("interact", interact) if interact is not None else None,
        pedagogy=DimensionFeedback("pedagogy", peda) if peda is not None else None,
    )


def test_select_best_prefers_pedagogy_then_recency():
    mem = [
        ({}, _fb(5, 5, 3, stage="pedagogy")),
        ({}, _fb(5, 5, 4, stage="pedagogy")),  # higher peda
        ({}, _fb(5, 5, 4, stage="pass")),       # tie peda, later → wins
    ]
    assert select_best(mem) == 2


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
