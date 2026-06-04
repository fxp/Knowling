"""Block registry (design §7).

Each registered block provides:
  * ``validate(content_spec)``        — sanity-check structured content
  * ``compile_prompt(block, kp)``     — instruction for an LLM to emit a block
  * ``template(block)``               — deterministic HTML fragment (offline /
                                        mock path; also the fallback renderer)

P0 implements text / quiz / param_sim. Declared-but-unimplemented block types
fall back to ``generic`` so specs never crash the pipeline.
"""

from __future__ import annotations

from typing import Any, Dict

from . import generic, param_sim, quiz, text

# type → module
REGISTRY = {
    "text": text,
    "quiz": quiz,
    "param_sim": param_sim,
}

IMPLEMENTED = tuple(REGISTRY.keys())


def get_block(block_type: str):
    return REGISTRY.get(block_type, generic)


def render_block_template(block: Dict[str, Any]) -> str:
    """Render one block dict → self-contained HTML fragment (mock/offline path)."""
    mod = get_block(block.get("type", "text"))
    return mod.template(block)


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    mod = get_block(block.get("type", "text"))
    return mod.compile_prompt(block, kp)


def validate(block: Dict[str, Any]) -> None:
    mod = get_block(block.get("type", "text"))
    mod.validate(block.get("content_spec", {}))


__all__ = [
    "REGISTRY",
    "IMPLEMENTED",
    "get_block",
    "render_block_template",
    "compile_prompt",
    "validate",
]
