"""``concept_graph`` block (design §7, ← Concept Explorer) — click node → highlight neighbors.

Self-contained inline canvas (no ECharts/CDN). Circular layout, hit-test clicks.

content_spec: { nodes: [{id, label}], edges: [{from, to}] }.
Invariant: clicking a node highlights its neighbors.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, jslit, scope as _scope

TYPE = "concept_graph"


def validate(content_spec: Dict[str, Any]) -> None:
    nodes = content_spec.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("concept_graph requires non-empty content_spec.nodes")
    for n in nodes:
        if "id" not in n:
            raise ValueError("each node needs an 'id'")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def has_canvas(html: str) -> bool:
        return "kl-cg-canvas" in _scope(html, bid)

    def clickable(html: str) -> bool:
        return "addEventListener('click'" in _scope(html, bid)

    return [
        {"id": f"{bid}.canvas", "description": "渲染概念图", "check": has_canvas,
         "gui_hint": "应展示节点-连线图"},
        {"id": f"{bid}.highlight", "description": "点击节点高亮邻居", "check": clickable,
         "gui_hint": "点击节点应高亮其相邻节点"},
    ]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return ("Render a concept graph on an inline <canvas> (no external libs). Nodes "
            "in a circular layout, edges as lines; clicking a node highlights it and "
            "its neighbors. Inline <script>. No external assets.")


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    bid = esc(block.get("block_id", "cg"))
    nodes = cs.get("nodes", [])
    edges = cs.get("edges", [])
    return f'''<section class="kl-block kl-conceptgraph" data-block-id="{bid}">
  <canvas class="kl-cg-canvas" width="640" height="360"></canvas>
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var nodes = {jslit(nodes)};
    var edges = {jslit(edges)};
    var canvas = root.querySelector('.kl-cg-canvas');
    var ctx = canvas.getContext('2d');
    var W = canvas.width, H = canvas.height, cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 50;
    var pos = {{}};
    nodes.forEach(function(n, k) {{
      var a = (k / nodes.length) * Math.PI * 2 - Math.PI / 2;
      pos[n.id] = {{ x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) }};
    }});
    function neighbors(id) {{
      var set = {{}};
      edges.forEach(function(e) {{
        if (e.from === id) set[e.to] = 1;
        if (e.to === id) set[e.from] = 1;
      }});
      return set;
    }}
    var active = null;
    function draw() {{
      ctx.clearRect(0, 0, W, H);
      var nb = active ? neighbors(active) : {{}};
      edges.forEach(function(e) {{
        var a = pos[e.from], b = pos[e.to];
        if (!a || !b) return;
        var hot = active && (e.from === active || e.to === active);
        ctx.strokeStyle = hot ? '#3056d3' : '#d0d7de';
        ctx.lineWidth = hot ? 2.5 : 1;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }});
      nodes.forEach(function(n) {{
        var p = pos[n.id];
        var hot = active === n.id, near = nb[n.id];
        ctx.fillStyle = hot ? '#e8590c' : (near ? '#3056d3' : '#8a93a2');
        ctx.beginPath(); ctx.arc(p.x, p.y, hot ? 12 : 9, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#1f2328'; ctx.font = '13px sans-serif'; ctx.textAlign = 'center';
        ctx.fillText(n.label || n.id, p.x, p.y - 16);
      }});
    }}
    canvas.addEventListener('click', function(ev) {{
      var rect = canvas.getBoundingClientRect();
      var mx = (ev.clientX - rect.left) * (W / rect.width);
      var my = (ev.clientY - rect.top) * (H / rect.height);
      active = null;
      nodes.forEach(function(n) {{
        var p = pos[n.id];
        if (Math.hypot(p.x - mx, p.y - my) < 16) active = n.id;
      }});
      draw();
    }});
    draw();
  }})();
  </script>
</section>'''
