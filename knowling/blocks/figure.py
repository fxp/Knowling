"""``figure`` block (design §7) — image/SVG + caption.

content_spec: { svg } inline SVG markup (preferred, self-contained), or { src }
data-URI / URL, plus optional { caption, alt }.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, scope as _scope

TYPE = "figure"


def validate(content_spec: Dict[str, Any]) -> None:
    if not content_spec.get("svg") and not content_spec.get("src"):
        raise ValueError("figure block requires content_spec.svg or content_spec.src")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def has_image(html: str) -> bool:
        seg = _scope(html, bid)
        return "<svg" in seg or "<img" in seg

    return [{"id": f"{bid}.image", "description": "图像成功渲染", "check": has_image,
             "gui_hint": "页面应展示该图像/SVG"}]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return ("Render a figure (inline SVG preferred, else <img>) with a <figcaption>. "
            "Self-contained, no external assets unless a data-URI. No <script>.")


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    bid = esc(block.get("block_id", "figure"))
    caption = cs.get("caption", "")
    if cs.get("svg"):
        media = cs["svg"]  # trusted inline svg from spec
    else:
        media = f'<img src="{esc(cs.get("src", ""))}" alt="{esc(cs.get("alt", caption))}">'
    cap = f'<figcaption>{esc(caption)}</figcaption>' if caption else ""
    return (
        f'<figure class="kl-block kl-figure" data-block-id="{bid}">\n'
        f'  {media}\n  {cap}\n</figure>'
    )
