"""``animation`` block (design §7) — controlled play / pause / replay.

content_spec: { keyframes: [str], autoplay?, interval_ms? }.
Cycles through keyframe captions/states; user can pause and replay.
Invariant: can pause and replay.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, jslit, count_tag, has_wiring, scope as _scope

TYPE = "animation"


def validate(content_spec: Dict[str, Any]) -> None:
    kf = content_spec.get("keyframes")
    if not isinstance(kf, list) or not kf:
        raise ValueError("animation requires non-empty content_spec.keyframes")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def has_controls(html: str) -> bool:
        seg = _scope(html, bid)
        return count_tag(seg, "<button") >= 1 and has_wiring(seg)

    return [{"id": f"{bid}.controls", "description": "可暂停/重播", "check": has_controls,
             "gui_hint": "应能暂停与重播动画"}]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return ("Render a controlled animation cycling keyframes with play/pause and "
            "replay buttons. Inline <script>, local state. No external assets.")


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    bid = esc(block.get("block_id", "anim"))
    keyframes = cs.get("keyframes", [])
    autoplay = bool(cs.get("autoplay", True))
    interval = int(cs.get("interval_ms", 1200))
    return f'''<section class="kl-block kl-animation" data-block-id="{bid}">
  <div class="kl-anim-stage"></div>
  <div class="kl-anim-nav">
    <button class="kl-anim-play" type="button"></button>
    <span class="kl-anim-frame"></span>
    <button class="kl-anim-replay" type="button">重播</button>
  </div>
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var frames = {jslit(keyframes)};
    var interval = {interval};
    var i = 0, timer = null, playing = false;
    var stage = root.querySelector('.kl-anim-stage');
    var frameLbl = root.querySelector('.kl-anim-frame');
    var playBtn = root.querySelector('.kl-anim-play');
    function render() {{
      stage.textContent = frames[i];
      frameLbl.textContent = (i + 1) + ' / ' + frames.length;
      playBtn.textContent = playing ? '暂停' : '播放';
    }}
    function tick() {{ i = (i + 1) % frames.length; render(); }}
    function play() {{ playing = true; timer = setInterval(tick, interval); render(); }}
    function pause() {{ playing = false; if (timer) clearInterval(timer); timer = null; render(); }}
    playBtn.addEventListener('click', function() {{ playing ? pause() : play(); }});
    root.querySelector('.kl-anim-replay').addEventListener('click', function() {{
      pause(); i = 0; render(); play();
    }});
    render();
    if ({jslit(autoplay)}) play();
  }})();
  </script>
</section>'''
