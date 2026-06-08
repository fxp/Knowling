"""manim block — render hook is exercised separately (needs the [manim] extra);
here we cover the zero-dep surface: validation, template, registration."""

import pytest

from knowling import blocks
from knowling.blocks import manim


def test_registered():
    assert blocks.REGISTRY.get("manim") is manim
    from knowling.schema.models import BLOCK_TYPES
    assert "manim" in BLOCK_TYPES


def test_validate_requires_script_and_scene():
    with pytest.raises(ValueError):
        manim.validate({"scene": "S"})
    with pytest.raises(ValueError):
        manim.validate({"script": "from manim import *"})
    manim.validate({"script": "from manim import *", "scene": "S"})  # ok


def test_template_with_video_embeds_video():
    block = {"block_id": "mv", "type": "manim", "content_spec": {
        "script": "x", "scene": "S", "caption": "抛物线",
        "video": "data:video/mp4;base64,AAAA"}}
    html = manim.template(block)
    assert '<video' in html and 'data:video/mp4;base64,AAAA' in html
    assert 'data-block-id="mv"' in html and "抛物线" in html


def test_template_without_video_shows_placeholder():
    block = {"block_id": "mv", "type": "manim", "content_spec": {
        "script": "x", "scene": "S", "caption": "待渲染", "render_error": "manim not installed"}}
    html = manim.template(block)
    assert "kl-manim-fallback" in html and "<video" not in html


def test_qa_assertion_accepts_video_or_placeholder():
    block = {"block_id": "mv", "type": "manim", "content_spec": {"script": "x", "scene": "S"}}
    checks = manim.qa_assertions(block)
    assert checks
    vid = manim.template({**block, "content_spec": {**block["content_spec"], "video": "data:video/mp4;base64,AAAA"}})
    ph = manim.template(block)
    assert checks[0]["check"](vid) and checks[0]["check"](ph)
