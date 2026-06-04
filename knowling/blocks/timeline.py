"""``timeline`` block (design §7) — click node to expand detail.

content_spec: { events: [{t, label, detail}] }.
Invariant: clicking a node reveals its detail.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, jslit, scope as _scope

TYPE = "timeline"


def validate(content_spec: Dict[str, Any]) -> None:
    events = content_spec.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("timeline requires non-empty content_spec.events")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def has_nodes(html: str) -> bool:
        return "kl-tl-node" in _scope(html, bid)

    def expandable(html: str) -> bool:
        return "addEventListener('click'" in _scope(html, bid)

    return [
        {"id": f"{bid}.nodes", "description": "渲染时间线节点", "check": has_nodes,
         "gui_hint": "应展示时间线节点"},
        {"id": f"{bid}.expand", "description": "点击节点展开详情", "check": expandable,
         "gui_hint": "点击节点应展开其详情"},
    ]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return ("Render a horizontal timeline of events; clicking a node shows its "
            "detail. Inline <script>, local state. No external assets.")


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    bid = esc(block.get("block_id", "tl"))
    events = cs.get("events", [])
    nodes = "\n".join(
        f'    <button class="kl-tl-node" data-i="{i}"><span class="kl-tl-t">{esc(e.get("t",""))}</span>'
        f'<span class="kl-tl-label">{esc(e.get("label",""))}</span></button>'
        for i, e in enumerate(events)
    )
    return f'''<section class="kl-block kl-timeline" data-block-id="{bid}">
  <div class="kl-tl-track">
{nodes}
  </div>
  <div class="kl-tl-detail" hidden></div>
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var events = {jslit(events)};
    var detail = root.querySelector('.kl-tl-detail');
    root.querySelectorAll('.kl-tl-node').forEach(function(node) {{
      node.addEventListener('click', function() {{
        root.querySelectorAll('.kl-tl-node').forEach(function(n) {{ n.classList.remove('is-active'); }});
        node.classList.add('is-active');
        var e = events[parseInt(node.dataset.i, 10)];
        detail.hidden = false;
        detail.textContent = e.detail || e.label || '';
      }});
    }});
  }})();
  </script>
</section>'''
