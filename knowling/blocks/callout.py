"""``callout`` block (design §7) — styled note box. content_spec: {variant, md}."""

from __future__ import annotations

from typing import Any, Dict

from ._common import esc, mini_markdown

TYPE = "callout"
_VARIANTS = {"info", "tip", "warning", "danger", "note"}


def validate(content_spec: Dict[str, Any]) -> None:
    if "md" not in content_spec:
        raise ValueError("callout block requires content_spec.md")


def qa_assertions(block: Dict[str, Any]):
    return []


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    return (
        "Render a callout box as a self-contained HTML fragment, no <script>.\n"
        f"variant: {cs.get('variant', 'note')}\nmarkdown: {cs.get('md', '')}\n"
        "Wrap in <aside class=\"kl-block kl-callout kl-callout-<variant>\">."
    )


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    variant = cs.get("variant", "note")
    if variant not in _VARIANTS:
        variant = "note"
    bid = esc(block.get("block_id", "callout"))
    body = mini_markdown(cs.get("md", ""))
    icon = {"info": "ℹ", "tip": "💡", "warning": "⚠", "danger": "⛔", "note": "🛈"}[variant]
    return (
        f'<aside class="kl-block kl-callout kl-callout-{variant}" data-block-id="{bid}">\n'
        f'  <span class="kl-callout-icon">{icon}</span>\n'
        f'  <div class="kl-callout-body">{body}</div>\n'
        f'</aside>'
    )
