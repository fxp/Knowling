"""``param_sim`` block — the heart of Knowling (design §7, Bret Victor style).

A "change a quantity and watch the result" explorable. Supports two natural
patterns, auto-detected from the expressions:

  * **slider-is-axis** (e.g. param ``x``, output ``x*x``): every expr variable is
    a slider, so the first output is plotted over the first param's range with a
    marker at the current value.
  * **parametric curve** (e.g. params ``A/ω/φ``, output ``A*Math.sin(x)``): the
    sliders are *parameters* and a free variable (``x``) is the horizontal sweep.
    Curve outputs (those mentioning the sweep var) are plotted as y = f(x) over
    the sweep range; scalar outputs (over params only, e.g. ``2*PI/w``) show as
    live numeric readouts.

content_spec:
  params:  [{name, label, min, max, step, default}]   # the sliders
  outputs: [{name, label, expr}]   # JS expr over param names (+ optional sweep var)
  x_range: [min, max]              # optional sweep range (default ≈ [-2π, 2π])
  explain: str

``expr`` is evaluated client-side via ``new Function`` inside the self-contained
artifact (local single-file; the QA loop guards behaviour).
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List

from ._common import esc, jslit, has_wiring, scope as _scope

TYPE = "param_sim"

_IDENT = re.compile(r"(?<![\.\w$])([A-Za-z_$][\w$]*)")
_RESERVED = {
    "Math", "PI", "E", "abs", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "sqrt", "cbrt", "pow", "exp", "log", "log2", "log10", "min", "max", "floor",
    "ceil", "round", "sign", "hypot", "true", "false", "null", "Infinity", "NaN",
    "return", "var", "let", "const",
}


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


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Explorable invariant (design §7): slider drives observable output."""
    bid = block.get("block_id", "")

    def has_slider(html: str) -> bool:
        return 'type="range"' in _scope(html, bid).lower()

    def wired_to_change(html: str) -> bool:
        return has_wiring(_scope(html, bid))

    return [
        {"id": f"{bid}.slider", "description": "渲染出可拖动滑块", "check": has_slider,
         "gui_hint": "页面应有 range 滑块控件"},
        {"id": f"{bid}.reactive", "description": "拖动滑块输出即时更新", "check": wired_to_change,
         "gui_hint": "拖动滑块后输出数值与曲线应立即变化"},
    ]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return (
        "Render this param_sim as a self-contained HTML fragment with inline\n"
        "<script>. Param sliders reshape a y = f(x) curve plotted over a sweep\n"
        "variable x; scalar outputs update live. Moving a slider must visibly\n"
        "change the curve. No external assets. Wrap in\n"
        "<section class=\"kl-block kl-paramsim\" data-block-id=\"%s\">.\n"
        "BlockSpec: %s\n" % (block.get("block_id", ""), jslit(block))
    )


def _default(p: Dict[str, Any]) -> float:
    if p.get("default") is not None:
        return p["default"]
    return round((float(p["min"]) + float(p["max"])) / 2, 4)


def _free_vars(expr: str) -> set:
    return {m.group(1) for m in _IDENT.finditer(expr or "")} - _RESERVED


def _analyze(params: List[Dict[str, Any]], outputs: List[Dict[str, Any]], cs: Dict[str, Any]):
    """Return (sweep, curves, scalars, legacy).

    sweep = {"name", "min", "max"}; curves/scalars are output lists.
    """
    pnames = {p["name"] for p in params}
    free = set()
    for o in outputs:
        free |= _free_vars(o.get("expr", ""))
    non_param = free - pnames

    if non_param:  # parametric: a sweep variable exists (prefer 'x')
        sweep_name = "x" if "x" in non_param else sorted(non_param)[0]
        rng = cs.get("x_range") or cs.get("xRange")
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            lo, hi = float(rng[0]), float(rng[1])
        else:
            lo, hi = -2 * math.pi, 2 * math.pi
        sweep = {"name": sweep_name, "min": lo, "max": hi}
        curves = [o for o in outputs if sweep_name in _free_vars(o.get("expr", ""))]
        scalars = [o for o in outputs if o not in curves]
        if not curves:  # safety
            curves = outputs[:1]
            scalars = outputs[1:]
        return sweep, curves, scalars, False

    # legacy: slider IS the axis — sweep over the first param, mark current value
    p0 = params[0]
    sweep = {"name": p0["name"], "min": float(p0["min"]), "max": float(p0["max"])}
    return sweep, outputs[:1], outputs[1:], True


def template(block: Dict[str, Any]) -> str:
    bid = esc(block.get("block_id", "paramsim"))
    cs = block.get("content_spec", {})
    params: List[Dict[str, Any]] = cs.get("params", [])
    outputs: List[Dict[str, Any]] = cs.get("outputs", [])
    explain: str = cs.get("explain", "")

    # normalize params (ensure a sensible default)
    pnorm = [{
        "name": p["name"], "label": p.get("label", p["name"]),
        "min": p["min"], "max": p["max"], "step": p.get("step", "any"),
        "default": _default(p),
    } for p in params]

    sweep, curves, scalars, legacy = _analyze(pnorm, outputs, cs)

    slider_html = "\n".join(
        f'''  <label class="kl-ps-ctl">
    <span class="kl-ps-name">{esc(p["label"])}</span>
    <input type="range" data-param="{esc(p["name"])}"
           min="{esc(p["min"])}" max="{esc(p["max"])}" step="{esc(p["step"])}"
           value="{esc(p["default"])}">
    <output class="kl-ps-val" data-for="{esc(p["name"])}"></output>
  </label>''' for p in pnorm
    )
    # readouts: scalar outputs always; in legacy mode also the curve value at marker
    readout_outs = list(scalars)
    if legacy and curves:
        readout_outs = curves[:1] + scalars
    out_html = "\n".join(
        f'  <div class="kl-ps-out"><span>{esc(o.get("label", o["name"]))}</span>'
        f'<strong data-out="{esc(o["name"])}">—</strong></div>'
        for o in readout_outs
    )

    return f'''<section class="kl-block kl-paramsim" data-block-id="{bid}">
  <div class="kl-ps-controls">
{slider_html}
  </div>
  <div class="kl-ps-outputs">
{out_html}
  </div>
  <canvas class="kl-ps-canvas" width="640" height="240"></canvas>
  {'<p class="kl-ps-explain">' + esc(explain) + '</p>' if explain else ''}
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var params = {jslit(pnorm)};
    var sweep = {jslit(sweep)};
    var curves = {jslit(curves)};
    var scalars = {jslit(readout_outs)};
    var legacy = {jslit(legacy)};
    var sliders = {{}};
    params.forEach(function(p) {{ sliders[p.name] = root.querySelector('input[data-param="' + p.name + '"]'); }});

    function vals() {{
      var v = {{}};
      params.forEach(function(p) {{ v[p.name] = parseFloat(sliders[p.name].value); }});
      return v;
    }}
    function ev(expr, ctx) {{
      try {{
        var ks = Object.keys(ctx);
        return new Function(ks.join(','), 'with(Math){{return (' + expr + ');}}')
          .apply(null, ks.map(function(k) {{ return ctx[k]; }}));
      }} catch (e) {{ return NaN; }}
    }}
    function fmt(n) {{
      if (typeof n !== 'number' || !isFinite(n)) return '—';
      return Math.abs(n) >= 1000 || (n !== 0 && Math.abs(n) < 0.01) ? n.toPrecision(4) : Math.round(n * 1000) / 1000;
    }}

    var canvas = root.querySelector('.kl-ps-canvas'), ctx2 = canvas.getContext('2d');
    var COLORS = ['#3056d3', '#e8590c', '#1a7f37', '#bf3989'];

    function plot(v) {{
      var W = canvas.width, H = canvas.height, pad = 30, N = 200;
      ctx2.clearRect(0, 0, W, H);
      var lo = sweep.min, hi = sweep.max;
      var series = curves.map(function(c) {{
        var pts = [], ymin = Infinity, ymax = -Infinity;
        for (var i = 0; i <= N; i++) {{
          var xv = lo + (hi - lo) * i / N;
          var probe = Object.assign({{}}, v); probe[sweep.name] = xv;
          var yv = ev(c.expr, probe);
          pts.push([xv, yv]);
          if (isFinite(yv)) {{ ymin = Math.min(ymin, yv); ymax = Math.max(ymax, yv); }}
        }}
        return {{ pts: pts, ymin: ymin, ymax: ymax }};
      }});
      var ymin = Math.min.apply(null, series.map(function(s) {{ return s.ymin; }}).filter(isFinite));
      var ymax = Math.max.apply(null, series.map(function(s) {{ return s.ymax; }}).filter(isFinite));
      if (!isFinite(ymin) || !isFinite(ymax) || ymin === ymax) {{ ymin = (ymin || 0) - 1; ymax = (ymax || 0) + 1; }}
      var sx = function(x) {{ return pad + (x - lo) / (hi - lo) * (W - 2 * pad); }};
      var sy = function(y) {{ return H - pad - (y - ymin) / (ymax - ymin) * (H - 2 * pad); }};
      // axes (x-axis at y=0 if in range, else bottom)
      ctx2.strokeStyle = '#d0d7de'; ctx2.lineWidth = 1;
      var y0 = (ymin <= 0 && ymax >= 0) ? sy(0) : H - pad;
      ctx2.beginPath(); ctx2.moveTo(pad, y0); ctx2.lineTo(W - pad, y0); ctx2.stroke();
      var x0 = (lo <= 0 && hi >= 0) ? sx(0) : pad;
      ctx2.beginPath(); ctx2.moveTo(x0, pad); ctx2.lineTo(x0, H - pad); ctx2.stroke();
      // curves
      series.forEach(function(s, ci) {{
        ctx2.strokeStyle = COLORS[ci % COLORS.length]; ctx2.lineWidth = 2; ctx2.beginPath();
        var started = false;
        s.pts.forEach(function(pt) {{
          if (!isFinite(pt[1])) {{ started = false; return; }}
          var px = sx(pt[0]), py = sy(pt[1]);
          if (!started) {{ ctx2.moveTo(px, py); started = true; }} else {{ ctx2.lineTo(px, py); }}
        }});
        ctx2.stroke();
      }});
      // legacy marker at the slider's current value
      if (legacy && curves.length) {{
        var mx = v[sweep.name], my = ev(curves[0].expr, v);
        if (isFinite(my)) {{ ctx2.fillStyle = '#e8590c'; ctx2.beginPath(); ctx2.arc(sx(mx), sy(my), 5, 0, Math.PI * 2); ctx2.fill(); }}
      }}
    }}

    function update() {{
      var v = vals();
      params.forEach(function(p) {{ root.querySelector('output[data-for="' + p.name + '"]').textContent = fmt(v[p.name]); }});
      scalars.forEach(function(o) {{
        var el = root.querySelector('[data-out="' + o.name + '"]');
        if (el) el.textContent = fmt(ev(o.expr, v));
      }});
      plot(v);
    }}
    params.forEach(function(p) {{ sliders[p.name].addEventListener('input', update); }});
    update();
  }})();
  </script>
</section>'''
