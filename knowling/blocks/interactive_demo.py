"""``interactive_demo`` block (design §7, a Knowling 重心) — general controls→outputs.

Generalizes param_sim beyond sliders: controls may be slider / number / select /
checkbox / text; outputs are JS expressions over control names.

content_spec:
  controls: [{name, label, kind, ...}]   # kind ∈ slider|number|select|checkbox|text
  outputs:  [{name, label, expr}]         # expr over control names
  explain?: str

Invariant (explorable): changing an input changes an observable output.
``expr`` is eval'd client-side via new Function (same trade-off as param_sim).
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, jslit, scope as _scope

TYPE = "interactive_demo"
_KINDS = {"slider", "number", "select", "checkbox", "text"}


def validate(content_spec: Dict[str, Any]) -> None:
    controls = content_spec.get("controls")
    outputs = content_spec.get("outputs")
    if not isinstance(controls, list) or not controls:
        raise ValueError("interactive_demo requires non-empty content_spec.controls")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("interactive_demo requires non-empty content_spec.outputs")
    for c in controls:
        if "name" not in c:
            raise ValueError("control missing 'name'")
        if c.get("kind", "slider") not in _KINDS:
            raise ValueError(f"control kind must be one of {_KINDS}")
    for o in outputs:
        if "name" not in o or "expr" not in o:
            raise ValueError("output needs 'name' and 'expr'")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def has_control(html: str) -> bool:
        return "data-ctl=" in _scope(html, bid)

    def has_output(html: str) -> bool:
        return "data-out=" in _scope(html, bid)

    def reactive(html: str) -> bool:
        seg = _scope(html, bid)
        return "addEventListener('input'" in seg or "addEventListener('change'" in seg

    return [
        {"id": f"{bid}.control", "description": "渲染出输入控件", "check": has_control,
         "gui_hint": "应有可操作的输入控件"},
        {"id": f"{bid}.output", "description": "存在可观察输出", "check": has_output,
         "gui_hint": "应展示随输入变化的输出"},
        {"id": f"{bid}.reactive", "description": "改输入即时改变输出", "check": reactive,
         "gui_hint": "改变输入后输出应立即更新"},
    ]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return ("Render an interactive demo: labeled controls (slider/number/select/"
            "checkbox/text) drive live output expressions. Changing any input must "
            "visibly change an output. Inline <script>, local state. No external assets.")


def _control_html(c: Dict[str, Any]) -> str:
    name = esc(c["name"])
    label = esc(c.get("label", c["name"]))
    kind = c.get("kind", "slider")
    if kind in ("slider", "number"):
        t = "range" if kind == "slider" else "number"
        return (f'<label class="kl-id-ctl"><span>{label}</span>'
                f'<input type="{t}" data-ctl="{name}" data-kind="{kind}" '
                f'min="{esc(c.get("min", 0))}" max="{esc(c.get("max", 10))}" '
                f'step="{esc(c.get("step", "any"))}" value="{esc(c.get("default", 0))}">'
                f'<output data-val="{name}"></output></label>')
    if kind == "select":
        opts = "".join(f'<option value="{esc(o)}">{esc(o)}</option>' for o in c.get("options", []))
        return (f'<label class="kl-id-ctl"><span>{label}</span>'
                f'<select data-ctl="{name}" data-kind="select">{opts}</select></label>')
    if kind == "checkbox":
        chk = "checked" if c.get("default") else ""
        return (f'<label class="kl-id-ctl"><span>{label}</span>'
                f'<input type="checkbox" data-ctl="{name}" data-kind="checkbox" {chk}></label>')
    return (f'<label class="kl-id-ctl"><span>{label}</span>'
            f'<input type="text" data-ctl="{name}" data-kind="text" value="{esc(c.get("default", ""))}"></label>')


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    bid = esc(block.get("block_id", "demo"))
    controls = cs.get("controls", [])
    outputs = cs.get("outputs", [])
    explain = cs.get("explain", "")
    ctl_html = "\n    ".join(_control_html(c) for c in controls)
    out_html = "\n    ".join(
        f'<div class="kl-id-out"><span>{esc(o.get("label", o["name"]))}</span>'
        f'<strong data-out="{esc(o["name"])}">—</strong></div>'
        for o in outputs
    )
    return f'''<section class="kl-block kl-interactivedemo" data-block-id="{bid}">
  <div class="kl-id-controls">
    {ctl_html}
  </div>
  <div class="kl-id-outputs">
    {out_html}
  </div>
  {'<p class="kl-id-explain">' + esc(explain) + '</p>' if explain else ''}
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var outputs = {jslit(outputs)};
    var ctls = Array.prototype.slice.call(root.querySelectorAll('[data-ctl]'));
    function readVals() {{
      var v = {{}};
      ctls.forEach(function(el) {{
        var k = el.dataset.kind, name = el.dataset.ctl;
        if (k === 'checkbox') v[name] = el.checked;
        else if (k === 'slider' || k === 'number') v[name] = parseFloat(el.value);
        else v[name] = el.value;
        var val = root.querySelector('[data-val="' + name + '"]');
        if (val) val.textContent = v[name];
      }});
      return v;
    }}
    function fmt(n) {{
      return (typeof n === 'number' && isFinite(n)) ? (Math.round(n * 1000) / 1000) : String(n);
    }}
    function update() {{
      var vals = readVals();
      var keys = Object.keys(vals);
      outputs.forEach(function(o) {{
        var out = root.querySelector('[data-out="' + o.name + '"]');
        try {{
          var fn = new Function(keys.join(','), 'return (' + o.expr + ');');
          out.textContent = fmt(fn.apply(null, keys.map(function(k) {{ return vals[k]; }})));
        }} catch (e) {{ out.textContent = 'NaN'; }}
      }});
    }}
    ctls.forEach(function(el) {{
      el.addEventListener('input', update);
      el.addEventListener('change', update);
    }});
    update();
  }})();
  </script>
</section>'''
