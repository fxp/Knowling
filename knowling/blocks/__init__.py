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

from . import (
    animation,
    audio,
    callout,
    code,
    concept_graph,
    deep_dive,
    figure,
    flashcards,
    generic,
    interactive_demo,
    param_sim,
    quiz,
    section,
    step_through,
    text,
    timeline,
    user_note,
)

# type → module (all 13 declared block types, design §4.3 / §7)
REGISTRY = {
    "text": text,
    "callout": callout,
    "figure": figure,
    "code": code,
    "section": section,
    "quiz": quiz,
    "flashcards": flashcards,
    "timeline": timeline,
    "concept_graph": concept_graph,
    "interactive_demo": interactive_demo,
    "param_sim": param_sim,
    "step_through": step_through,
    "animation": animation,
    "audio": audio,
    "deep_dive": deep_dive,
    "user_note": user_note,
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


def qa_assertions(block: Dict[str, Any]):
    """Return this block's interaction invariants (design §7 qa_assertions)."""
    mod = get_block(block.get("type", "text"))
    fn = getattr(mod, "qa_assertions", None)
    return fn(block) if fn else []


__all__ = [
    "REGISTRY",
    "IMPLEMENTED",
    "get_block",
    "render_block_template",
    "compile_prompt",
    "validate",
    "qa_assertions",
]
