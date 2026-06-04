"""P0 closed-loop tests — run with the offline MockProvider (no API key)."""

import json
import os

import pytest

from knowling.blocks import param_sim, quiz, text
from knowling.engine import Config, generate_knowling
from knowling.schema import BlockSpec, KnowledgePoint, KnowlingSpec


def _kp():
    return KnowledgePoint(
        id="calc.derivative.chain-rule",
        title="链式法则",
        description="复合函数的求导法则",
        learning_objectives=["能对复合函数求导"],
        difficulty="core",
    )


def _cfg(qa=True):
    from knowling.capabilities.qa import QAConfig

    return Config(provider_name="mock", quiet=True, qa_enabled=qa,
                  qa=QAConfig(sandbox_name="static"))


def test_full_loop_no_qa(tmp_path):
    out = tmp_path / "k.html"
    k = generate_knowling(_kp(), _cfg(qa=False), out_path=str(out))
    assert k.status == "draft"  # QA skipped → never "ready"
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "kl-paramsim" in html and "kl-quiz" in html
    assert "http://" not in html.replace("http://www.w3.org", "")
    assert k.spec.knowledge_point_id == "calc.derivative.chain-rule"
    assert len(k.model_trace) >= 2


def test_full_loop_with_qa_ready(tmp_path):
    out = tmp_path / "k.html"
    k = generate_knowling(_kp(), _cfg(qa=True), out_path=str(out))
    # mock templates satisfy all three dimensions → ready
    assert k.status == "ready"
    assert k.qa.passed is True
    assert k.qa.score_interact == 5.0
    assert k.qa.score_render is not None and k.qa.score_peda is not None


def test_spec_roundtrips():
    cfg = Config(provider_name="mock", quiet=True)
    from knowling.capabilities import spec_planner
    from knowling.providers import get_provider

    spec, _ = spec_planner.plan(_kp(), None, get_provider("mock", quiet=True))
    d = spec.to_dict()
    spec2 = KnowlingSpec.from_dict(json.loads(json.dumps(d)))
    assert spec2.to_dict() == d


def test_text_block_markdown():
    html = text.template({"type": "text", "content_spec": {"md": "## Hi\n**bold** and `code`"}})
    assert "<h2>Hi</h2>" in html
    assert "<strong>bold</strong>" in html
    assert "<code>code</code>" in html


def test_quiz_invariants_present():
    """QA invariant (design §7): wrong choice shows explanation; right marks correct."""
    block = {
        "type": "quiz", "block_id": "q1",
        "content_spec": {"question": "Q", "options": ["a", "b"], "answer": 1, "explain": "because"},
    }
    quiz.validate(block["content_spec"])
    html = quiz.template(block)
    assert "is-correct" in html and "is-wrong" in html
    assert "because" in html
    assert 'data-block-id="q1"' in html


def test_quiz_validation_rejects_bad_answer():
    with pytest.raises(ValueError):
        quiz.validate({"question": "Q", "options": ["a", "b"], "answer": 5})


def test_param_sim_invariants_present():
    """Explorable invariant: a slider exists and an output expr is wired."""
    block = {
        "type": "param_sim", "block_id": "p1",
        "content_spec": {
            "params": [{"name": "x", "min": 0, "max": 10, "default": 2}],
            "outputs": [{"name": "y", "label": "y", "expr": "x * x"}],
        },
    }
    param_sim.validate(block["content_spec"])
    html = param_sim.template(block)
    assert 'type="range"' in html
    assert 'data-param="x"' in html
    assert "x * x" in html  # expr drives observable output


def test_param_sim_validation_requires_params():
    with pytest.raises(ValueError):
        param_sim.validate({"params": [], "outputs": [{"name": "y", "expr": "1"}]})


def test_unknown_block_falls_back_to_generic():
    from knowling.blocks import render_block_template

    html = render_block_template({"type": "timeline", "block_id": "t1", "content_spec": {}})
    assert "未实现块类型" in html and "timeline" in html


def test_difficulty_validation():
    with pytest.raises(ValueError):
        KnowledgePoint(id="x", title="t", difficulty="impossible")
