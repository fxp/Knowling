"""``deep_dive`` block (design §7) — collapsible disclosure.

content_spec: { summary, expanded_md }.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, mini_markdown, has_wiring, scope as _scope

TYPE = "deep_dive"


def validate(content_spec: Dict[str, Any]) -> None:
    if "summary" not in content_spec:
        raise ValueError("deep_dive block requires content_spec.summary")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def toggles(html: str) -> bool:
        seg = _scope(html, bid).lower()
        return "<details" in seg or has_wiring(seg)

    return [{"id": f"{bid}.toggle", "description": "可展开/收起", "check": toggles,
             "gui_hint": "点击摘要应展开/收起详情"}]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return "Render a <details>/<summary> disclosure. Native toggle, no <script> needed."


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    bid = esc(block.get("block_id", "deepdive"))
    body = mini_markdown(cs.get("expanded_md", ""))
    return (
        f'<details class="kl-block kl-deepdive" data-block-id="{bid}">\n'
        f'  <summary>{esc(cs.get("summary", ""))}</summary>\n'
        f'  <div class="kl-deepdive-body">{body}</div>\n</details>'
    )
