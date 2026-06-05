"""Fidelity guard — cards must stay on their knowledge point (anti-drift)."""

from knowling.capabilities import fidelity
from knowling.capabilities.qa import QAConfig
from knowling.engine import Config, generate_knowling, refine_knowling
from knowling.providers import get_provider
from knowling.schema import BlockSpec, KnowledgePoint, KnowlingSpec, Pedagogy

KP = KnowledgePoint(id="calc.chain", title="链式法则", description="复合函数求导")
MOCK = get_provider("mock", quiet=True)


def _spec(md):
    return KnowlingSpec(knowledge_point_id="calc.chain",
                        blocks=[BlockSpec(block_id="t", type="text", content_spec={"md": md})])


def test_heuristic_passes_on_topic():
    fb = fidelity.assess(_spec("## 链式法则\n复合函数的链式法则。"), KP, MOCK)
    assert fb.ok and fb.score >= 3.0


def test_heuristic_flags_drift():
    fb = fidelity.assess(_spec("## 导数\n导数是切线斜率。"), KP, MOCK)
    assert not fb.ok


def test_spec_text_collects_block_content():
    spec = KnowlingSpec(
        knowledge_point_id="k", pedagogy=Pedagogy(hook="HOOK"),
        blocks=[
            BlockSpec(block_id="q", type="quiz",
                      content_spec={"question": "QPROMPT", "options": ["a"], "answer": 0, "explain": "EXP"}),
            BlockSpec(block_id="s", type="step_through",
                      content_spec={"steps": [{"state": "ST", "explain": "SE"}]}),
        ])
    text = fidelity.spec_text(spec)
    for marker in ("HOOK", "QPROMPT", "EXP", "ST", "SE"):
        assert marker in text


def test_refine_attaches_fidelity_and_stays_on_topic():
    cfg = Config(provider_name="mock", quiet=True, qa=QAConfig(sandbox_name="static"))
    base = generate_knowling(KP, cfg)
    # a relationship question must NOT turn the card into a different topic
    new, summary = refine_knowling(base.spec, KP, "这个和导数是什么关系？", cfg)
    assert hasattr(new, "_fidelity")
    assert new._fidelity["on_topic"] is True  # original 链式法则 blocks kept
    # the original knowledge point is preserved
    assert new.spec.knowledge_point_id == "calc.chain"
