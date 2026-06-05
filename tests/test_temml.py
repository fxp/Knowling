"""Temml backend — compile-time LaTeX → MathML (optional; skipped if no Node)."""

import pytest

from knowling.blocks import _temml
from knowling.blocks._math import render

pytestmark = pytest.mark.skipif(not _temml.available(),
                                reason="Temml/Node not available")


def test_temml_renders_mathml(monkeypatch):
    monkeypatch.setenv("KNOWLING_MATH", "auto")
    out = render(r"T = \frac{2\pi}{\omega}", display=True)
    assert "<math" in out and "<mfrac" in out
    assert "\\frac" not in out and "$" not in out


def test_temml_handles_full_latex(monkeypatch):
    monkeypatch.setenv("KNOWLING_MATH", "auto")
    # constructs the pure-Python fallback can't do — matrices / cases
    out = render(r"\begin{cases} x & x>0 \\ -x & x\le 0 \end{cases}")
    assert "<math" in out  # rendered, not dropped


def test_fallback_when_disabled(monkeypatch):
    monkeypatch.setenv("KNOWLING_MATH", "fallback")
    out = render(r"\frac{a}{b}")
    assert "<math" not in out and "kl-frac" in out


def test_direct_render_returns_mathml():
    mathml = _temml.render(r"x^2 + y^2", display=False)
    assert mathml and "<math" in mathml and "<msup" in mathml
