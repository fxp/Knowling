"""Fallback for declared-but-unimplemented block types (design §7 roadmap).

Renders a labeled placeholder so a spec using e.g. ``timeline`` still produces a
valid artifact in P0 instead of crashing.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from ._common import esc

TYPE = "generic"


def validate(content_spec: Dict[str, Any]) -> None:
    return None


def qa_assertions(block: Dict[str, Any]):
    return []  # unimplemented placeholder — nothing to assert


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return (
        f"Render block type '{block.get('type')}' as a self-contained HTML "
        "fragment. No external assets.\n"
        f"BlockSpec: {json.dumps(block, ensure_ascii=False)}\n"
    )


def template(block: Dict[str, Any]) -> str:
    btype = esc(block.get("type", "unknown"))
    intent = esc(block.get("intent", ""))
    pretty = esc(json.dumps(block.get("content_spec", {}), ensure_ascii=False, indent=2))
    return (
        f'<section class="kl-block kl-generic" data-block-id="{esc(block.get("block_id",""))}">\n'
        f'  <p class="kl-generic-tag">未实现块类型：<code>{btype}</code></p>\n'
        f'  <p class="kl-generic-intent">{intent}</p>\n'
        f'  <details><summary>content_spec</summary><pre>{pretty}</pre></details>\n'
        f'</section>'
    )
