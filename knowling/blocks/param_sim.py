"""``param_sim`` block — the heart of Knowling (design §7, Bret Victor style).

Sliders drive expressions; outputs update live and a canvas plots the first
output across the first param's range with the current point marked. This is
the "change a quantity and watch the result" explorable.

content_spec:
  params:  [{name, label, min, max, step, default}]
  outputs: [{name, label, expr}]   # expr: JS expression over param names
  explain: str
  viz:     optional {x, y}         # which param/output to plot (defaults to first)

Note: ``expr`` is evaluated client-side via ``new Function`` inside the
self-contained artifact. Acceptable for P0 (local, single-file). When LLM-authored
code-gen lands with the QA loop (P1), the sandbox + invariants guard this.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, jslit

TYPE = "param_sim"


def validate(content_spec: Dict[str, Any]) -> None:
    params = content_spec.get("params")
    outputs = content_spec.get("outputs")
    if not isinstance(params, list) or not params:
        raise ValueError("param_sim requires non-empty content_spec.params")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("param_sim requires non-empty content_spec.outputs")
    for p in params:
        for k in ("name", "min", "max"):
            if k not in p:
                raise ValueError(f"param_sim param missing '{k}': {p}")
    for o in outputs:
        for k in ("name", "expr"):
            if k not in o:
                raise ValueError(f"param_sim output missing '{k}': {o}")


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return (
        "Render this param_sim as a self-contained HTML fragment with inline\n"
        "<script>. Each param → a labeled <input type=range>; outputs recompute\n"
        "live on input; include a small <canvas> plotting the first output across\n"
        "the first param's range with the current value marked. The explorable\n"
        "invariant: moving a slider must visibly change the observable output.\n"
        "No external assets, no localStorage. Wrap in\n"
        "<section class=\"kl-block kl-paramsim\" data-block-id=\"%s\">.\n"
        "BlockSpec: %s\n" % (block.get("block_id", ""), jslit(block))
    )


def _default(p: Dict[str, Any]) -> float:
    if "default" in p:
        return p["default"]
    return (float(p["min"]) + float(p["max"])) / 2


def template(block: Dict[str, Any]) -> str:
    bid = esc(block.get("block_id", "paramsim"))
    cs = block.get("content_spec", {})
    params: List[Dict[str, Any]] = cs.get("params", [])
    outputs: List[Dict[str, Any]] = cs.get("outputs", [])
    explain: str = cs.get("explain", "")
    viz = cs.get("viz") or {}
    x_param = viz.get("x", params[0]["name"])
    y_output = viz.get("y", outputs[0]["name"])

    slider_html = []
    for p in params:
        name = esc(p["name"])
        label = esc(p.get("label", p["name"]))
        step = p.get("step", "any")
        slider_html.append(
            f'''  <label class="kl-ps-ctl">
    <span class="kl-ps-name">{label}</span>
    <input type="range" data-param="{name}"
           min="{esc(p['min'])}" max="{esc(p['max'])}" step="{esc(step)}"
           value="{esc(_default(p))}">
    <output class="kl-ps-val" data-for="{name}"></output>
  </label>'''
        )
    out_html = "\n".join(
        f'  <div class="kl-ps-out"><span>{esc(o.get("label", o["name"]))}</span>'
        f'<strong data-out="{esc(o["name"])}">—</strong></div>'
        for o in outputs
    )

    return f'''<section class="kl-block kl-paramsim" data-block-id="{bid}">
  <div class="kl-ps-controls">
{chr(10).join(slider_html)}
  </div>
  <div class="kl-ps-outputs">
{out_html}
  </div>
  <canvas class="kl-ps-canvas" width="640" height="220"></canvas>
  {'<p class="kl-ps-explain">' + esc(explain) + '</p>' if explain else ''}
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var params = {jslit(params)};
    var outputs = {jslit(outputs)};
    var xParam = {jslit(x_param)};
    var yOutput = {jslit(y_output)};
    var sliders = {{}};
    params.forEach(function(p) {{
      sliders[p.name] = root.querySelector('input[data-param="' + p.name + '"]');
    }});

    function readVals() {{
      var v = {{}};
      params.forEach(function(p) {{ v[p.name] = parseFloat(sliders[p.name].value); }});
      return v;
    }}
    function evalOut(o, vals) {{
      try {{
        var fn = new Function(Object.keys(vals).join(','), 'return (' + o.expr + ');');
        return fn.apply(null, Object.keys(vals).map(function(k) {{ return vals[k]; }}));
      }} catch (e) {{ return NaN; }}
    }}
    function fmt(n) {{
      if (typeof n !== 'number' || !isFinite(n)) return String(n);
      return Math.abs(n) >= 1000 || (n !== 0 && Math.abs(n) < 0.01)
        ? n.toPrecision(4) : Math.round(n * 1000) / 1000;
    }}

    var canvas = root.querySelector('.kl-ps-canvas');
    var ctx = canvas.getContext('2d');
    var xp = params.filter(function(p) {{ return p.name === xParam; }})[0] || params[0];
    var yo = outputs.filter(function(o) {{ return o.name === yOutput; }})[0] || outputs[0];

    function plot(vals) {{
      var W = canvas.width, H = canvas.height, pad = 28;
      ctx.clearRect(0, 0, W, H);
      var N = 120, xs = [], ys = [];
      var lo = parseFloat(xp.min), hi = parseFloat(xp.max);
      var ymin = Infinity, ymax = -Infinity;
      for (var i = 0; i <= N; i++) {{
        var xv = lo + (hi - lo) * i / N;
        var probe = Object.assign({{}}, vals); probe[xp.name] = xv;
        var yv = evalOut(yo, probe);
        xs.push(xv); ys.push(yv);
        if (isFinite(yv)) {{ ymin = Math.min(ymin, yv); ymax = Math.max(ymax, yv); }}
      }}
      if (!isFinite(ymin) || !isFinite(ymax) || ymin === ymax) {{ ymin -= 1; ymax += 1; }}
      function sx(x) {{ return pad + (x - lo) / (hi - lo) * (W - 2 * pad); }}
      function sy(y) {{ return H - pad - (y - ymin) / (ymax - ymin) * (H - 2 * pad); }}
      // axes
      ctx.strokeStyle = '#d0d7de'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(pad, H - pad); ctx.lineTo(W - pad, H - pad); ctx.stroke();
      // curve
      ctx.strokeStyle = '#3056d3'; ctx.lineWidth = 2; ctx.beginPath();
      var started = false;
      for (var j = 0; j <= N; j++) {{
        if (!isFinite(ys[j])) {{ started = false; continue; }}
        var px = sx(xs[j]), py = sy(ys[j]);
        if (!started) {{ ctx.moveTo(px, py); started = true; }} else {{ ctx.lineTo(px, py); }}
      }}
      ctx.stroke();
      // current point
      var cx = sx(vals[xp.name]), cy = sy(evalOut(yo, vals));
      ctx.fillStyle = '#e8590c';
      ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2); ctx.fill();
    }}

    function update() {{
      var vals = readVals();
      params.forEach(function(p) {{
        root.querySelector('output[data-for="' + p.name + '"]').textContent = fmt(vals[p.name]);
      }});
      outputs.forEach(function(o) {{
        root.querySelector('[data-out="' + o.name + '"]').textContent = fmt(evalOut(o, vals));
      }});
      plot(vals);
    }}
    params.forEach(function(p) {{ sliders[p.name].addEventListener('input', update); }});
    update();
  }})();
  </script>
</section>'''
