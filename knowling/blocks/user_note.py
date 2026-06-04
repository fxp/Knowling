"""``user_note`` block (design §7) — in-memory note textarea.

content_spec: { placeholder }. State is component-local (no localStorage, §10.2).
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, scope as _scope

TYPE = "user_note"


def validate(content_spec: Dict[str, Any]) -> None:
    return None


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def has_input(html: str) -> bool:
        return "<textarea" in _scope(html, bid)

    return [{"id": f"{bid}.input", "description": "可输入笔记", "check": has_input,
             "gui_hint": "应能在文本框中输入文字"}]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return "Render a note <textarea> (in-memory only, no localStorage). No external assets."


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    bid = esc(block.get("block_id", "note"))
    ph = esc(cs.get("placeholder", "在此记录你的想法…"))
    return (
        f'<section class="kl-block kl-usernote" data-block-id="{bid}">\n'
        f'  <textarea class="kl-usernote-area" rows="4" placeholder="{ph}"></textarea>\n'
        f'</section>'
    )
