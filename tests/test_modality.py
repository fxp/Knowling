"""Modality guarantee: every card must carry rich media (visual/interactive/
audio). The planner re-plans once if the first draft is text-only."""

import json

from knowling.capabilities import spec_planner
from knowling.providers.base import Completion
from knowling.schema import KnowledgePoint, KnowlingSpec, BlockSpec


def _kp():
    return KnowledgePoint(id="k", title="某知识点", description="d", difficulty="core")


def _spec_json(types):
    return json.dumps({
        "knowledge_point_id": "k",
        "pedagogy": {"hook": "h"},
        "blocks": [{"block_id": f"b{i}", "type": t,
                    "content_spec": ({"md": "x"} if t in ("text", "callout")
                                     else {"params": [{"name": "x", "min": 0, "max": 5}],
                                           "outputs": [{"name": "y", "expr": "x*x"}]} if t == "param_sim"
                                     else {"question": "?", "options": ["a", "b"], "answer": 0})}
                   for i, t in enumerate(types)],
        "render_target": "html", "version": 1,
    }, ensure_ascii=False)


class _StubProvider:
    name = "stub"

    def __init__(self, replies):
        self.replies = replies
        self.calls = 0

    def complete(self, messages, *, task="generic", **kw):
        text = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return Completion(text=text, model="stub", provider="stub")


def test_has_visual_detects_media():
    visual = KnowlingSpec(knowledge_point_id="k", blocks=[
        BlockSpec(block_id="a", type="text"), BlockSpec(block_id="b", type="param_sim")])
    text_only = KnowlingSpec(knowledge_point_id="k", blocks=[
        BlockSpec(block_id="a", type="text"), BlockSpec(block_id="b", type="quiz")])
    assert spec_planner._has_visual(visual) is True
    assert spec_planner._has_visual(text_only) is False


def test_text_only_plan_triggers_reated_replan():
    # first draft is text-only → planner re-plans once; second draft has param_sim
    prov = _StubProvider([_spec_json(["text", "quiz"]), _spec_json(["text", "param_sim", "quiz"])])
    spec, call = spec_planner.plan(_kp(), None, prov)
    assert prov.calls == 2  # repaired
    assert spec_planner._has_visual(spec) is True
    assert "param_sim" in [b.type for b in spec.blocks]


def test_visual_plan_no_replan():
    prov = _StubProvider([_spec_json(["text", "param_sim", "quiz"])])
    spec, call = spec_planner.plan(_kp(), None, prov)
    assert prov.calls == 1  # already has media → no second call
    assert spec_planner._has_visual(spec) is True
