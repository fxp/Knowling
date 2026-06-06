"""P2 — all 13 block types validate, render, and satisfy their own assertions."""

import pytest

from knowling import blocks
from knowling.assembler import assemble_html
from knowling.capabilities.qa import QAConfig, gui_agent
from knowling.providers import get_provider
from knowling.sandbox import get_sandbox
from knowling.schema import BLOCK_TYPES, BlockSpec, KnowlingSpec

SAMPLES = {
    "text": {"md": "# T\nbody"},
    "callout": {"variant": "tip", "md": "note"},
    "figure": {"svg": "<svg width='30' height='30'><rect width='30' height='30'/></svg>", "caption": "c"},
    "code": {"lang": "py", "code": "print(1)"},
    "section": {"title": "S"},
    "quiz": {"question": "Q", "options": ["a", "b"], "answer": 1, "explain": "x"},
    "flashcards": {"cards": [{"front": "f", "back": "b"}]},
    "timeline": {"events": [{"t": "2020", "label": "a", "detail": "d"}]},
    "concept_graph": {"nodes": [{"id": "n1", "label": "A"}, {"id": "n2", "label": "B"}],
                      "edges": [{"from": "n1", "to": "n2"}]},
    "interactive_demo": {"controls": [{"name": "a", "kind": "slider", "min": 0, "max": 10, "default": 2}],
                         "outputs": [{"name": "o", "label": "o", "expr": "a*2"}]},
    "param_sim": {"params": [{"name": "x", "min": 0, "max": 5, "default": 1}],
                  "outputs": [{"name": "y", "label": "y", "expr": "x*x"}]},
    "step_through": {"steps": [{"state": "s0", "explain": "e0"}, {"state": "s1", "explain": "e1"}]},
    "animation": {"keyframes": ["a", "b"], "autoplay": False},
    "audio": {"waveform": "sine", "explain": "听",
              "controls": [{"name": "f", "label": "频率", "min": 110, "max": 880, "default": 440, "maps": "frequency"}]},
    "deep_dive": {"summary": "more", "expanded_md": "detail"},
    "user_note": {"placeholder": "note"},
}


def test_every_declared_type_has_sample():
    assert set(SAMPLES) == set(BLOCK_TYPES)


@pytest.mark.parametrize("btype", list(SAMPLES))
def test_block_validates_renders_and_passes_assertions(btype):
    b = BlockSpec(block_id=f"b-{btype}", type=btype, content_spec=SAMPLES[btype])
    blocks.validate(b.to_dict())
    frag = blocks.render_block_template(b.to_dict())
    assert f'data-block-id="b-{btype}"' in frag
    spec = KnowlingSpec(knowledge_point_id="k", blocks=[b])
    html = assemble_html(spec, [frag], "T")
    render = get_sandbox("static").render_and_screenshot(html)
    fb = gui_agent.test(render, [b.to_dict()], get_provider("mock", quiet=True),
                        QAConfig(sandbox_name="static"))
    assert fb.passed, f"{btype} failed: {fb.suggestions}"


@pytest.mark.parametrize("btype,bad", [
    ("flashcards", {"cards": []}),
    ("step_through", {"steps": []}),
    ("interactive_demo", {"controls": [], "outputs": [{"name": "y", "expr": "1"}]}),
    ("concept_graph", {"nodes": []}),
    ("timeline", {"events": []}),
])
def test_validation_rejects_empty(btype, bad):
    with pytest.raises(ValueError):
        blocks.get_block(btype).validate(bad)
