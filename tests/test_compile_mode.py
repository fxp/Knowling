"""compile_mode: template (default, consistent) vs codegen (LLM per block)."""

import pytest

from knowling.capabilities import block_compiler
from knowling.providers.base import Completion, LLMProvider
from knowling.schema import BlockSpec, KnowledgePoint

KP = KnowledgePoint(id="k", title="T")


class _BoomProvider(LLMProvider):
    """A non-mock provider that explodes if .complete is ever called."""
    name = "boom"

    def __init__(self):
        super().__init__("boom-1")

    def complete(self, messages, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("template mode must not call the model")


def _block():
    return BlockSpec(block_id="ps", type="param_sim",
                     content_spec={"params": [{"name": "x", "min": 0, "max": 5, "default": 1}],
                                   "outputs": [{"name": "y", "label": "y", "expr": "x*x"}]})


def test_template_mode_makes_no_model_call():
    html, call = block_compiler.compile(_block(), KP, None, _BoomProvider(), mode="template")
    assert 'data-block-id="ps"' in html
    assert call.provider == "template" and call.cost_usd == 0.0


def test_template_mode_is_the_default():
    # default mode == template → still no model call from the Boom provider
    html, call = block_compiler.compile(_block(), KP, None, _BoomProvider())
    assert call.provider == "template"


def test_template_output_uses_kl_design_system():
    """Consistency: template-rendered blocks share the .kl-* classes."""
    html, _ = block_compiler.compile(_block(), KP, None, _BoomProvider())
    assert "kl-block" in html and "kl-paramsim" in html


def test_codegen_mode_invokes_provider():
    """mode=codegen routes through the LLM (here: returns a usable fragment)."""
    class _StubProvider(LLMProvider):
        name = "stub"
        def __init__(self):
            super().__init__("stub-1")
        def complete(self, messages, **kwargs):
            return Completion(text='<section class="x"><input type="range"></section>',
                              model="stub-1", provider="stub")

    html, call = block_compiler.compile(_block(), KP, None, _StubProvider(), mode="codegen")
    assert call.provider == "stub"
    assert 'data-block-id="ps"' in html  # injected even though LLM omitted it
