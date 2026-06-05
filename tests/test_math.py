"""Pure-Python fallback math rendering (no KaTeX/MathJax/Temml).

These tests pin the pure-Python fallback, so they force KNOWLING_MATH=fallback
(the dispatcher would otherwise use Temml→MathML when Node is available — see
test_temml.py for that path)."""

import pytest

from knowling.blocks import quiz, step_through
from knowling.blocks._common import mathspan, mini_markdown
from knowling.blocks._math import has_math, render_math


@pytest.fixture(autouse=True)
def _force_fallback(monkeypatch):
    monkeypatch.setenv("KNOWLING_MATH", "fallback")


def test_greek_and_functions():
    out = render_math(r"y = A\sin(\omega x + \phi)")
    assert "ω" in out and "φ" in out
    assert ">sin<" in out  # function name, upright
    assert "\\" not in out and "$" not in out


def test_fraction():
    out = render_math(r"T = \frac{2\pi}{\omega}")
    assert "kl-frac" in out and "kl-num" in out and "kl-den" in out
    assert "2π" in out and "ω" in out


def test_superscript_subscript():
    assert "<sup>n</sup>" in render_math(r"(1+r)^n")
    assert "<sub>0</sub>" in render_math(r"x_0")
    assert "<sup>2</sup>" in render_math(r"x^{2}")


def test_sqrt_and_relations():
    assert "kl-sqrt" in render_math(r"\sqrt{2}")
    assert "≤" in render_math(r"a \leq b")
    assert "×" in render_math(r"a \times b")


def test_markdown_renders_inline_math_no_leak():
    html = mini_markdown(r"周期 $T = \frac{2\pi}{\omega}$，振幅 $A$。")
    assert "kl-frac" in html
    assert "$" not in html and "\\frac" not in html


def test_mathspan_escapes_plain_and_renders_math():
    out = mathspan(r"角度 <ω> 与 $\theta$")
    assert "&lt;ω&gt;" in out          # plain text still escaped
    assert "θ" in out                  # math rendered
    assert "$" not in out


def test_has_math():
    assert has_math(r"$x^2$") and has_math(r"$$y$$")
    assert not has_math("no math here")


def test_blocks_embed_rendered_math_for_js_fields():
    # step_through state with math → pre-rendered HTML in the data, innerHTML used
    st = step_through.template({"block_id": "s", "type": "step_through",
                                "content_spec": {"steps": [{"state": r"$y = 2\sin(x)$", "explain": "x"}]}})
    assert "kl-math" in st and "innerHTML" in st and "\\sin" not in st
    qz = quiz.template({"block_id": "q", "type": "quiz",
                        "content_spec": {"question": r"$x^2$ 的导数?", "options": ["$2x$", "x"], "answer": 0}})
    # jslit escapes "</" → "<\\/", so check the opening tag + math wrapper
    assert "<sup>2" in qz and "kl-math" in qz and "innerHTML" in qz
