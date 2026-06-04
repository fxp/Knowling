"""``text`` block — static narrative (design §7). content_spec: {md}."""

from __future__ import annotations

from typing import Any, Dict

from ._common import esc, mini_markdown

TYPE = "text"


def validate(content_spec: Dict[str, Any]) -> None:
    if "md" not in content_spec:
        raise ValueError("text block requires content_spec.md")


def qa_assertions(block: Dict[str, Any]):
    return []  # static narrative — no interaction invariants


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    return (
        "Render this narrative text block as a self-contained HTML fragment.\n"
        "Wrap it in <section class=\"kl-block kl-text\">…</section>.\n"
        "Use semantic HTML; no external assets; no <script>.\n"
        f"intent: {block.get('intent','')}\n"
        f"markdown content:\n{cs.get('md','')}\n"
    )


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    body = mini_markdown(cs.get("md", ""))
    bid = esc(block.get("block_id", "text"))
    return f'<section class="kl-block kl-text" data-block-id="{bid}">\n{body}\n</section>'
