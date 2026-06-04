"""Focused tests for the quiz block — the assessment core (single-KP scope)."""

import pytest

from knowling.assembler import assemble_html
from knowling.blocks import quiz
from knowling.capabilities.qa import QAConfig, gui_agent
from knowling.providers import get_provider
from knowling.sandbox import get_sandbox
from knowling.schema import BlockSpec, KnowlingSpec

MULTI = {
    "title": "小测",
    "questions": [
        {"type": "single", "prompt": "1+1=?", "options": ["1", "2", "3"], "answer": 1, "explain": "是2"},
        {"type": "multi", "prompt": "选偶数", "options": ["1", "2", "3", "4"], "answer": [1, 3], "explain": "2,4"},
        {"type": "boolean", "prompt": "地球是圆的", "answer": True, "explain": "对"},
        {"type": "fill", "prompt": "水的化学式", "answer": "H2O", "accept": ["水"], "explain": "H2O"},
    ],
}


def _check(cs):
    b = BlockSpec(block_id="qz", type="quiz", content_spec=cs)
    quiz.validate(cs)
    frag = quiz.template(b.to_dict())
    html = assemble_html(KnowlingSpec(knowledge_point_id="k", blocks=[b]), [frag], "T")
    r = get_sandbox("static").render_and_screenshot(html)
    return gui_agent.test(r, [b.to_dict()], get_provider("mock", quiet=True),
                          QAConfig(sandbox_name="static"))


def test_backcompat_single():
    fb = _check({"question": "Q?", "options": ["a", "b"], "answer": 1, "explain": "因为b"})
    assert fb.passed


def test_multi_question_set_scores():
    fb = _check(MULTI)
    assert fb.passed
    frag = quiz.template({"block_id": "qz", "type": "quiz", "content_spec": MULTI})
    assert "kl-quiz-score" in frag  # multi-question → scoring UI


def test_boolean_normalizes_to_options():
    qs = quiz._normalize({"questions": [{"type": "boolean", "prompt": "p", "answer": False}]})
    assert qs[0]["type"] == "single"
    assert qs[0]["options"] == ["正确", "错误"]
    assert qs[0]["answer"] == 1  # False → 错误 index


@pytest.mark.parametrize("bad", [
    {"questions": [{"type": "single", "prompt": "x", "options": ["a"], "answer": 0}]},
    {"questions": [{"type": "multi", "prompt": "x", "options": ["a", "b"], "answer": [9]}]},
    {"questions": [{"type": "fill", "prompt": "x"}]},
    {"questions": [{"type": "single", "prompt": "", "options": ["a", "b"], "answer": 0}]},
])
def test_validation_rejects(bad):
    with pytest.raises(ValueError):
        quiz.validate(bad)
