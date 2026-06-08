"""``audio`` block — the auditory modality: hear the concept, not just see it.

A 2D waveform canvas (the visual) fused with a real Web Audio oscillator (the
sound). Sliders mapped to ``frequency`` / ``gain`` / ``detune`` change both the
drawn wave and the played tone live — so amplitude → loudness, frequency → pitch
are *felt*, not just read. Self-contained (Web Audio is built into browsers).

content_spec:
  waveform: "sine" | "square" | "sawtooth" | "triangle"   (default "sine")
  controls: [{name, label, min, max, step, default, maps}] # maps ∈ frequency|gain|detune
  explain:  str
If controls are omitted, a sensible frequency + volume pair is used.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, jslit, has_wiring, mathspan, scope as _scope

TYPE = "audio"
_WAVES = {"sine", "square", "sawtooth", "triangle"}
_MAPS = {"frequency", "gain", "detune"}

_DEFAULT_CONTROLS = [
    {"name": "freq", "label": "频率 (Hz)", "min": 110, "max": 880, "step": 1, "default": 440, "maps": "frequency"},
    {"name": "vol", "label": "音量", "min": 0, "max": 1, "step": 0.01, "default": 0.3, "maps": "gain"},
]


def _controls(cs: Dict[str, Any]) -> List[Dict[str, Any]]:
    cl = cs.get("controls") or _DEFAULT_CONTROLS
    out = []
    for c in cl:
        maps = c.get("maps")
        if maps not in _MAPS:
            maps = "frequency" if "freq" in str(c.get("name", "")).lower() else "gain"
        out.append({
            "name": c["name"], "label": c.get("label", c["name"]),
            "min": c.get("min", 0), "max": c.get("max", 1),
            "step": c.get("step", "any"),
            "default": c.get("default", (float(c.get("min", 0)) + float(c.get("max", 1))) / 2),
            "maps": maps,
        })
    return out


def validate(content_spec: Dict[str, Any]) -> None:
    if content_spec.get("waveform") and content_spec["waveform"] not in _WAVES:
        raise ValueError(f"audio waveform must be one of {_WAVES}")
    for c in content_spec.get("controls", []) or []:
        if "name" not in c:
            raise ValueError("audio control needs a 'name'")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def has_play(html: str) -> bool:
        return "kl-audio-play" in _scope(html, bid)

    def makes_sound(html: str) -> bool:
        seg = _scope(html, bid)
        return "AudioContext" in seg and has_wiring(seg)

    return [
        {"id": f"{bid}.play", "description": "有播放/停止控件", "check": has_play,
         "gui_hint": "应有播放声音的按钮"},
        {"id": f"{bid}.sound", "description": "可发声且随滑块变化", "check": makes_sound,
         "gui_hint": "点击播放应发声，拖动滑块音高/响度随之变化"},
    ]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return ("Render an audio explorable: a waveform <canvas> + a play/stop button "
            "+ sliders mapped to a Web Audio oscillator's frequency/gain. Moving a "
            "slider changes both the drawn wave and the played tone. No external "
            "assets. Wrap in <section class=\"kl-block kl-audio\" data-block-id=\"%s\">."
            % block.get("block_id", ""))


def template(block: Dict[str, Any]) -> str:
    bid = esc(block.get("block_id", "audio"))
    cs = block.get("content_spec", {})
    waveform = cs.get("waveform", "sine")
    if waveform not in _WAVES:
        waveform = "sine"
    controls = _controls(cs)
    explain = cs.get("explain", "")

    sliders = "\n".join(
        f'''  <label class="kl-au-ctl">
    <span class="kl-au-name">{mathspan(c["label"])}</span>
    <input type="range" data-ctl="{esc(c["name"])}" data-maps="{esc(c["maps"])}"
           min="{esc(c["min"])}" max="{esc(c["max"])}" step="{esc(c["step"])}" value="{esc(c["default"])}">
    <output class="kl-au-val" data-for="{esc(c["name"])}"></output>
  </label>''' for c in controls
    )

    return f'''<section class="kl-block kl-audio" data-block-id="{bid}">
  <canvas class="kl-au-canvas" width="640" height="180"></canvas>
  <div class="kl-au-controls">
{sliders}
  </div>
  <div class="kl-au-bar">
    <button class="kl-audio-play" type="button">▶ 播放</button>
    <span class="kl-au-hint">{'<span class="kl-au-explain">' + mathspan(explain) + '</span>' if explain else '拖动滑块，边看波形边听声音'}</span>
  </div>
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var waveform = {jslit(waveform)};
    var controls = {jslit(controls)};
    var sliders = {{}};
    controls.forEach(function(c) {{ sliders[c.name] = root.querySelector('input[data-ctl="' + c.name + '"]'); }});
    var ctx = null, osc = null, gainNode = null, playing = false;
    var btn = root.querySelector('.kl-audio-play');
    var canvas = root.querySelector('.kl-au-canvas'), g = canvas.getContext('2d');

    function mapped(kind) {{
      var c = controls.filter(function(c) {{ return c.maps === kind; }})[0];
      return c ? parseFloat(sliders[c.name].value) : null;
    }}
    function start() {{
      if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
      if (ctx.state === 'suspended') ctx.resume();
      osc = ctx.createOscillator(); gainNode = ctx.createGain();
      osc.type = waveform;
      var f = mapped('frequency'); if (f != null) osc.frequency.value = f;
      var d = mapped('detune'); if (d != null) osc.detune.value = d;
      var v = mapped('gain'); gainNode.gain.value = (v != null ? v : 0.3);
      osc.connect(gainNode); gainNode.connect(ctx.destination);
      osc.start(); playing = true; btn.textContent = '⏸ 停止'; btn.classList.add('is-playing');
    }}
    function stop() {{
      if (osc) {{ try {{ osc.stop(); }} catch (e) {{}} osc.disconnect(); osc = null; }}
      playing = false; btn.textContent = '▶ 播放'; btn.classList.remove('is-playing');
    }}
    btn.addEventListener('click', function() {{ playing ? stop() : start(); }});
    document.addEventListener('visibilitychange', function() {{ if (document.hidden && playing) stop(); }});
    // stop sound when the host (e.g. card deck) switches away from this card
    window.addEventListener('knowling:stop-media', function() {{ if (playing) stop(); }});

    function draw() {{
      var W = canvas.width, H = canvas.height, pad = 14, mid = H / 2;
      g.clearRect(0, 0, W, H);
      g.strokeStyle = '#d0d7de'; g.lineWidth = 1;
      g.beginPath(); g.moveTo(0, mid); g.lineTo(W, mid); g.stroke();
      var f = mapped('frequency'), v = mapped('gain');
      var amp = (v != null ? v : 0.5) * (mid - pad);
      // cycles shown grow with frequency (relative to the slider's low end)
      var fc = controls.filter(function(c) {{ return c.maps === 'frequency'; }})[0];
      var lo = fc ? parseFloat(fc.min) || 1 : 1;
      var cycles = f != null ? Math.max(0.5, f / lo) : 3;
      var shapes = {{
        sine: function(t) {{ return Math.sin(t); }},
        square: function(t) {{ return Math.sin(t) >= 0 ? 1 : -1; }},
        triangle: function(t) {{ return 2 / Math.PI * Math.asin(Math.sin(t)); }},
        sawtooth: function(t) {{ var x = t / (2 * Math.PI); return 2 * (x - Math.floor(x + 0.5)); }}
      }};
      var fn = shapes[waveform] || shapes.sine;
      g.strokeStyle = '#3056d3'; g.lineWidth = 2; g.beginPath();
      for (var px = 0; px <= W; px++) {{
        var t = (px / W) * cycles * 2 * Math.PI;
        var y = mid - amp * fn(t);
        if (px === 0) g.moveTo(px, y); else g.lineTo(px, y);
      }}
      g.stroke();
    }}
    function update() {{
      controls.forEach(function(c) {{
        root.querySelector('output[data-for="' + c.name + '"]').textContent = parseFloat(sliders[c.name].value);
      }});
      if (playing) {{
        var f = mapped('frequency'); if (f != null && osc) osc.frequency.value = f;
        var d = mapped('detune'); if (d != null && osc) osc.detune.value = d;
        var v = mapped('gain'); if (v != null && gainNode) gainNode.gain.value = v;
      }}
      draw();
    }}
    controls.forEach(function(c) {{ sliders[c.name].addEventListener('input', update); }});
    update();
  }})();
  </script>
</section>'''
