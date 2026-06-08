"""Block compiler (design §5 ④, §10.2) — BlockSpec → self-contained HTML fragment.

Two modes:
  * ``template`` (default): render via the block's deterministic template using
    the LLM-*planned* content_spec. Every block shares the .kl-* design system,
    so a component looks uniform and blocks are reliable — the consistency path.
  * ``codegen``: the LLM writes bespoke HTML/JS per block (more variety, but
    inconsistent style + occasional breakage). For novel/unsupported blocks.

The intelligence lives in planning (what blocks, what content); presentation is
unified by the templates. The offline mock always renders via templates.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

from .. import blocks
from ..providers.base import LLMProvider
from ..schema import BlockSpec, KnowledgePoint, ModelCall
from ._extract import extract_html

SYSTEM = (
    "你是前端工程师。把 BlockSpec 编译成一个自包含的 HTML 片段。"
    "无外部运行时依赖；交互状态用内联 <script> 的组件内变量(禁止 localStorage)；"
    "可调量必须真实驱动可观察输出的变化。只输出 HTML 片段，不要解释。"
)

PROMPT_TEMPLATE = """把以下 BlockSpec 编译成一个自包含的 HTML 片段。
约束:
- 无外部运行时依赖; 所有状态用内联 <script> 的组件内变量(禁止 localStorage)。
- 实现 interaction_spec.controls; 保证 interaction_spec.invariants 成立。
- explorable 准则: 可调量必须真实驱动可观察输出的变化。
- 用 <section class="kl-block kl-{type}" data-block-id="{block_id}"> 包裹。
- 风格简洁，沿用页面已有的 .kl-* 设计令牌。
只输出 HTML 片段。

知识点: {kp_title}
{compile_hint}"""


def _render_manim(block_dict: dict, text_provider=None, vlm_provider=None) -> None:
    """Render a manim block → inline data-URI into its content_spec.

    Three paths: (a) ``video`` already present → skip; (b) a ready ``script`` →
    render directly; (c) only an ``animate`` intent → author the Scene with the
    visual-review loop (needs real LLM + VLM). Mutates content_spec in place;
    sets ``render_error`` + leaves a placeholder on any failure. Never raises."""
    cs = block_dict.setdefault("content_spec", {})
    if cs.get("video"):
        return
    from . import manim_render
    if not manim_render.available():
        cs["render_error"] = "manim toolchain not installed"
        return
    scene = cs.get("scene") or "GeneratedScene"

    if not cs.get("script"):
        animate = cs.get("animate")
        if not animate:
            cs["render_error"] = "manim block needs `script` or `animate`"
            return
        if text_provider is None or getattr(text_provider, "name", "mock") == "mock":
            cs["render_error"] = "manim authoring needs a real LLM provider"
            return
        from . import manim_author
        res = manim_author.author(animate, scene, text_provider, vlm_provider, max_rounds=4)
        if res:
            cs.update({"script": res["script"], "scene": res["scene"],
                       "video": res["video"], "review": res["review"]})
        else:
            cs["render_error"] = "manim authoring failed to render"
        return

    uri, err = manim_render.render_data_uri(cs["script"], scene)
    if uri:
        cs["video"] = uri
    else:
        cs["render_error"] = err


def _looks_usable(html: str, block: BlockSpec) -> bool:
    if not html or len(html.strip()) < 20:
        return False
    low = html.lower()
    if "<section" not in low and "<div" not in low:
        return False
    return True


def _ensure_block_id(html: str, block_id: str, btype: str) -> str:
    """Guarantee the fragment's outer element carries data-block-id.

    LLM codegen doesn't always honor the wrapper instruction; scope(),
    qa_assertions and the render heuristic all key off data-block-id, so we
    inject it rather than trust compliance (design §3.1 #3 — traceable blocks)."""
    if not block_id or f'data-block-id="{block_id}"' in html:
        return html
    m = re.search(r"<([a-zA-Z][\w-]*)", html)
    if not m:
        return (f'<section class="kl-block kl-{btype}" data-block-id="{block_id}">\n'
                f'{html}\n</section>')
    insert_at = m.end(1)
    return html[:insert_at] + f' data-block-id="{block_id}"' + html[insert_at:]


def compile(
    block: BlockSpec,
    kp: KnowledgePoint,
    grounding: Optional[List[Any]],
    provider: LLMProvider,
    suggestions: Optional[List[str]] = None,
    mode: str = "template",
    vlm_provider: Optional[LLMProvider] = None,
) -> Tuple[str, ModelCall]:
    """Compile a BlockSpec → self-contained HTML fragment.

    mode="template" (default): render via the block's deterministic template
      using the (LLM-planned) content_spec. This is the consistency path — every
      block shares the .kl-* design system, so a component looks uniform and the
      blocks are reliable. No per-block model call.
    mode="codegen": the LLM writes bespoke HTML/JS for the block (more visual
      variety, but inconsistent style + occasional breakage). For novel blocks.
    """
    block_dict = block.to_dict()

    # validate structured content up front (raises with a clear message)
    blocks.validate(block_dict)

    # manim block: render the Scene script → inline MP4 (optional [manim] toolchain).
    # Degrades to a captioned placeholder if the toolchain is absent or render fails.
    if block.type == "manim":
        _render_manim(block_dict, text_provider=provider, vlm_provider=vlm_provider)

    # template path (default) — consistent styling, deterministic, no LLM call.
    # Mock provider always lands here regardless of mode.
    if mode != "codegen" or provider.name == "mock":
        html = blocks.render_block_template(block_dict)
        call = ModelCall(stage="compile", provider="template", model="-", cost_usd=0.0)
        return html, call

    # codegen path: LLM generates the block code
    hint = blocks.compile_prompt(block_dict, kp.to_dict())
    if grounding:
        from .retriever import format_grounding, GroundingChunk

        gtext = grounding if isinstance(grounding, str) else format_grounding(
            [g for g in grounding if isinstance(g, GroundingChunk)]
        )
        if gtext:
            hint += "\n\n依据材料(事实须与此一致):\n" + gtext
    if suggestions:
        hint += "\n\n质检反馈(请据此修复):\n- " + "\n- ".join(suggestions)
    user = PROMPT_TEMPLATE.format(
        type=block.type,
        block_id=block.block_id,
        kp_title=kp.title,
        compile_hint=hint,
    )
    comp = provider.complete(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        task="compile_block",
        temperature=0.3,
        max_tokens=8000,
        thinking="disabled",
        meta={"block": block_dict, "kp": kp.to_dict()},
    )
    html = extract_html(comp.text)
    if not _looks_usable(html, block):
        # resilience: fall back to the deterministic template
        html = blocks.render_block_template(block_dict)
    else:
        html = _ensure_block_id(html, block.block_id, block.type)

    call = ModelCall(
        stage="compile",
        provider=comp.provider,
        model=comp.model,
        prompt_tokens=comp.prompt_tokens,
        completion_tokens=comp.completion_tokens,
        cost_usd=comp.cost_usd,
    )
    return html, call
