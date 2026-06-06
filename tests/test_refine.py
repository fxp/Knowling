"""Chat-driven refine: current card spec + instruction → a new card (offline)."""

import pytest

from knowling.capabilities import refine
from knowling.capabilities.qa import QAConfig
from knowling.engine import Config, generate_knowling, refine_knowling
from knowling.providers import get_provider
from knowling.schema import KnowledgePoint
from knowling.studio import StudioState


def _cfg():
    return Config(provider_name="mock", quiet=True, qa=QAConfig(sandbox_name="static"))


def _kp():
    return KnowledgePoint(id="calc.chain", title="链式法则", description="复合函数求导",
                          difficulty="core", audience="高中生")


def test_refine_keeps_kp_id_and_bumps_version():
    cfg, kp = _cfg(), _kp()
    base = generate_knowling(kp, cfg)
    new_spec, call, summary, changes = refine.refine(base.spec, kp, "随便", get_provider("mock", quiet=True))
    assert new_spec.knowledge_point_id == base.spec.knowledge_point_id
    assert new_spec.version == base.spec.version + 1
    assert summary


@pytest.mark.parametrize("instruction,expect_type", [
    ("太难了，简单点", "callout"),
    ("讲深一点", "deep_dive"),
    ("举个具体例子", "text"),
    ("这个和导数是什么关系？", "callout"),
])
def test_refine_adds_relevant_block(instruction, expect_type):
    cfg, kp = _cfg(), _kp()
    base = generate_knowling(kp, cfg)
    new, summary, changes = refine_knowling(base.spec, kp, instruction, cfg)
    types_before = [b.type for b in base.spec.blocks]
    types_after = [b.type for b in new.spec.blocks]
    assert len(types_after) == len(types_before) + 1
    assert expect_type in types_after
    assert new._html and "kl-card" in new._html  # compiles to a real card
    assert new.status in ("ready", "qa_failed")
    # the diff is described: model/mock change bullets + deterministic block delta
    assert changes and any("📦" in c for c in changes)
    assert getattr(new, "_changes", None) == changes


def test_block_delta_describes_added_block():
    from knowling.capabilities.refine import block_delta
    from knowling.schema import BlockSpec, KnowlingSpec
    old = KnowlingSpec(knowledge_point_id="k", blocks=[BlockSpec(block_id="a", type="text")])
    new = KnowlingSpec(knowledge_point_id="k", blocks=[
        BlockSpec(block_id="a", type="text"), BlockSpec(block_id="b", type="callout")])
    d = block_delta(old, new)
    assert "1→2" in d and "+1 callout" in d


def test_refine_produces_a_new_distinct_card():
    cfg, kp = _cfg(), _kp()
    base = generate_knowling(kp, cfg)
    new, _summary, _changes = refine_knowling(base.spec, kp, "太难了", cfg)
    assert new._html != base._html  # the fixed state changed


def test_studio_state_generate_then_refine():
    state = StudioState(_kp(), _cfg())
    state.generate()
    assert state.version == 1 and "kl-card" in state.card_html
    _k, summary = state.refine("讲深一点")
    assert state.version == 2 and summary
    assert "kl-deepdive" in state.card_html or "deep" in state.card_html.lower()
