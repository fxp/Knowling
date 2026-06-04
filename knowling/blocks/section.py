"""``section`` block (design §7) — heading / divider. content_spec: {title, md?}."""

from __future__ import annotations

from typing import Any, Dict

from ._common import esc, mini_markdown

TYPE = "section"


def validate(content_spec: Dict[str, Any]) -> None:
    if "title" not in content_spec:
        raise ValueError("section block requires content_spec.title")


def qa_assertions(block: Dict[str, Any]):
    return []


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    return f"Render a section heading/divider. title: {cs.get('title','')}. No <script>."


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    bid = esc(block.get("block_id", "section"))
    sub = mini_markdown(cs.get("md", "")) if cs.get("md") else ""
    return (
        f'<section class="kl-block kl-section" data-block-id="{bid}">\n'
        f'  <h2 class="kl-section-title">{esc(cs.get("title", ""))}</h2>\n'
        f'  {sub}\n</section>'
    )
