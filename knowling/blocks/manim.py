"""``manim`` block — 3Blue1Brown-style rendered animation (optional [manim]).

Unlike the other (zero-dep, browser-rendered) blocks, this one carries a
ManimCommunity ``Scene`` script that is rendered to MP4 at *compile* time
(see ``capabilities/manim_render``) and inlined as a ``data:`` URI so the card
stays a single file. If the toolchain is absent or the render fails, the block
degrades to a captioned placeholder rather than breaking the card.

content_spec:
  script:  str   # a complete ManimCommunity python script (one Scene subclass)
  scene:   str   # the Scene class name to render
  caption: str   # shown under the video
  video:   str   # data: URI, filled in by the compile step (do not author)
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, mathspan, scope as _scope

TYPE = "manim"


def validate(content_spec: Dict[str, Any]) -> None:
    # Either a ready Scene script, or an `animate` intent the compile step authors.
    if not content_spec.get("script") and not content_spec.get("animate"):
        raise ValueError("manim block requires content_spec.script or content_spec.animate")
    if not content_spec.get("scene"):
        raise ValueError("manim block requires content_spec.scene (the Scene class name)")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def has_media(html: str) -> bool:
        seg = _scope(html, bid).lower()
        return "<video" in seg or "kl-manim-fallback" in seg

    return [
        {"id": f"{bid}.media", "description": "渲染出动画视频(或占位)", "check": has_media,
         "gui_hint": "应出现一个可播放的动画视频"},
    ]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return (
        "Write a ManimCommunity (manim v0.19) Scene that animates this concept.\n"
        "STRICT: output only a complete python script with exactly ONE Scene subclass;\n"
        "no markdown, no explanation. Do NOT use Tex/MathTex/Title (LaTeX is absent) —\n"
        "use Text(...) for all labels. Prefer Axes/NumberPlane/plot, shapes, FadeIn,\n"
        "Create, Transform, Indicate. Keep it ~6-12s. content_spec must be "
        '{"script": <the script>, "scene": <class name>, "caption": <short caption>}.\n'
        "BlockSpec intent: %s" % block.get("intent", "")
    )


def _placeholder(caption: str, note: str = "") -> str:
    sub = f'<p class="kl-manim-cap">{caption}</p>' if caption else ""
    hint = f'<p class="kl-manim-note">{esc(note)}</p>' if note else ""
    return (f'<div class="kl-manim-fallback">🎬 动画待渲染（需 [manim] 渲染环境）{hint}</div>{sub}')


def template(block: Dict[str, Any]) -> str:
    bid = esc(block.get("block_id", "manim"))
    cs = block.get("content_spec", {})
    caption = mathspan(cs.get("caption", ""))
    video = cs.get("video", "")
    if video:
        cap = f'<figcaption class="kl-manim-cap">{caption}</figcaption>' if caption else ""
        body = (f'<video class="kl-manim-video" controls playsinline preload="metadata">'
                f'<source src="{esc(video)}" type="video/mp4"></video>{cap}')
    else:
        body = _placeholder(caption, cs.get("render_error", ""))
    return (f'<section class="kl-block kl-manim" data-block-id="{bid}">\n'
            f'  <figure class="kl-manim-fig">{body}</figure>\n'
            f'</section>')
