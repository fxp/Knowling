"""Robustness against real LLM codegen: block-id injection + semantic assertions.

LLM-generated blocks use their own markup/classes, so QA must key off behavior
(controls + JS wiring), not our template's class names, and the compiler must
guarantee a traceable data-block-id even when the model omits it.
"""

from knowling.assembler import assemble_html
from knowling.blocks import qa_assertions
from knowling.capabilities.block_compiler import _ensure_block_id
from knowling.capabilities.qa import QAConfig, gui_agent
from knowling.providers import get_provider
from knowling.sandbox import get_sandbox
from knowling.schema import BlockSpec, KnowlingSpec


def test_ensure_block_id_injects_when_missing():
    html = '<section class="my-quiz"><p>Q</p></section>'
    out = _ensure_block_id(html, "b1", "quiz")
    assert 'data-block-id="b1"' in out
    assert out.startswith('<section data-block-id="b1"')  # injected after tag name


def test_ensure_block_id_noop_when_present():
    html = '<div data-block-id="b1">x</div>'
    assert _ensure_block_id(html, "b1", "quiz") == html


def test_ensure_block_id_wraps_when_no_tag():
    out = _ensure_block_id("just text", "b1", "text")
    assert 'data-block-id="b1"' in out and "<section" in out


def _passes(block_dict, html_fragment):
    spec = KnowlingSpec(knowledge_point_id="k", blocks=[BlockSpec.from_dict(block_dict)])
    html = assemble_html(spec, [html_fragment], "T")
    r = get_sandbox("static").render_and_screenshot(html)
    fb = gui_agent.test(r, [block_dict], get_provider("mock", quiet=True),
                        QAConfig(sandbox_name="static"))
    return fb


def test_semantic_quiz_passes_with_foreign_markup():
    """A quiz written in non-Knowling markup still satisfies the invariants."""
    block = {"block_id": "qz", "type": "quiz",
             "content_spec": {"question": "Q", "options": ["a", "b"], "answer": 0}}
    foreign = '''<section data-block-id="qz">
      <p>Q</p>
      <button class="opt">a</button><button class="opt">b</button>
      <script>document.querySelectorAll('.opt').forEach(function(b){
        b.addEventListener('click', function(){ b.style.background='#cfc'; });});</script>
    </section>'''
    assert _passes(block, foreign).passed


def test_semantic_param_sim_passes_with_foreign_markup():
    block = {"block_id": "ps", "type": "param_sim",
             "content_spec": {"params": [{"name": "x", "min": 0, "max": 5}],
                              "outputs": [{"name": "y", "expr": "x*x"}]}}
    foreign = '''<div data-block-id="ps">
      <input type="range" id="s" min="0" max="5">
      <span id="o">0</span>
      <script>document.getElementById('s').addEventListener('input', function(e){
        document.getElementById('o').textContent = e.target.value * e.target.value; });</script>
    </div>'''
    assert _passes(block, foreign).passed


def test_step_through_accepts_llm_synonyms():
    """GLM emitted {title, describe}; we must accept it as {state, explain}."""
    from knowling.blocks import step_through as st

    cs = {"steps": [{"title": "S0", "describe": "first"},
                    {"title": "S1", "describe": "second"}]}
    st.validate(cs)  # no raise
    norm = st._steps(cs)
    assert norm[0] == {"state": "S0", "explain": "first"}
    frag = st.template({"block_id": "st", "type": "step_through", "content_spec": cs})
    assert "S0" in frag and "first" in frag

    # a step with no state-like key at all is still rejected
    import pytest
    with pytest.raises(ValueError):
        st.validate({"steps": [{"foo": "bar"}]})


def test_semantic_quiz_fails_without_wiring():
    """A static, non-interactive quiz must still fail interaction."""
    block = {"block_id": "qz", "type": "quiz",
             "content_spec": {"question": "Q", "options": ["a", "b"], "answer": 0}}
    dead = '<section data-block-id="qz"><p>Q</p><button>a</button><button>b</button></section>'
    assert not _passes(block, dead).passed
