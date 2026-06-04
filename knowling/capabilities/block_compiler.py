"""Block compiler (design §5 ④, §10.2) — BlockSpec → self-contained HTML fragment.

Per the chosen P0 strategy, the LLM directly generates block HTML/JS. When the
provider is the offline mock (or when generated output is unusable), we fall
back to the block's deterministic template so the loop always closes.
"""

from __future__ import annotations

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


def _looks_usable(html: str, block: BlockSpec) -> bool:
    if not html or len(html.strip()) < 20:
        return False
    low = html.lower()
    if "<section" not in low and "<div" not in low:
        return False
    return True


def compile(
    block: BlockSpec,
    kp: KnowledgePoint,
    grounding: Optional[List[Any]],
    provider: LLMProvider,
) -> Tuple[str, ModelCall]:
    block_dict = block.to_dict()

    # validate structured content up front (raises with a clear message)
    blocks.validate(block_dict)

    # mock path: deterministic template, no model round-trip
    if provider.name == "mock":
        html = blocks.render_block_template(block_dict)
        comp = provider.complete(
            [{"role": "user", "content": "compile"}],
            task="compile_block",
            meta={"block": block_dict, "kp": kp.to_dict()},
        )
        call = ModelCall(
            stage="compile",
            provider=comp.provider,
            model=comp.model,
            prompt_tokens=comp.prompt_tokens,
            completion_tokens=comp.completion_tokens,
            cost_usd=comp.cost_usd,
        )
        # comp.text already IS the template (mock._compile_block), prefer it
        return (comp.text or html), call

    # real provider: LLM generates the block code
    user = PROMPT_TEMPLATE.format(
        type=block.type,
        block_id=block.block_id,
        kp_title=kp.title,
        compile_hint=blocks.compile_prompt(block_dict, kp.to_dict()),
    )
    comp = provider.complete(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        task="compile_block",
        temperature=0.3,
        meta={"block": block_dict, "kp": kp.to_dict()},
    )
    html = extract_html(comp.text)
    if not _looks_usable(html, block):
        # resilience: fall back to the deterministic template
        html = blocks.render_block_template(block_dict)

    call = ModelCall(
        stage="compile",
        provider=comp.provider,
        model=comp.model,
        prompt_tokens=comp.prompt_tokens,
        completion_tokens=comp.completion_tokens,
        cost_usd=comp.cost_usd,
    )
    return html, call
