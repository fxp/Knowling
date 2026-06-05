"""QA loop — backtrack + select-best (design §6.2), three-dimensional.

``qa_step`` evaluates render → interact → pedagogy in order, short-circuiting at
the first dimension that fails (design §6.1). ``qa_loop`` drives steps, recompiles
only the failed blocks (design §3.1 #3), backtracks after repeated render errors,
and finally selects the best step by peda → interact → render → recency.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from ...assembler import assemble_html
from ...providers.base import LLMProvider
from ...sandbox import get_sandbox
from ...sandbox.base import Sandbox
from ...schema import KnowlingSpec, QAReport
from .. import block_compiler
from . import gui_agent, pedagogy_judge, render_vlm
from .types import QAConfig, StepFeedback

EventSink = Callable[[str, dict], None]


def _noop(kind: str, payload: dict) -> None:
    return None


# ─────────────────────────── single step ───────────────────────────


def qa_step(
    artifact_html: str,
    spec: KnowlingSpec,
    kp,
    providers: Dict[str, LLMProvider],
    sandbox: Sandbox,
    cfg: QAConfig,
    grounding: Optional[List[Any]] = None,
) -> StepFeedback:
    block_ids = [b.block_id for b in spec.blocks]
    spec_blocks = [b.to_dict() for b in spec.blocks]

    render = sandbox.render_and_screenshot(artifact_html, label=spec.knowledge_point_id)

    f_render = render_vlm.assess(render, block_ids, providers["render"], cfg)
    if not f_render.passed:
        return StepFeedback(stage="render", render=f_render)

    f_interact = gui_agent.test(render, spec_blocks, providers["gui"], cfg)
    if not f_interact.passed:
        return StepFeedback(stage="interact", render=f_render, interact=f_interact)

    f_peda = pedagogy_judge.assess(
        render.html, spec, kp, grounding, providers["judge"], cfg
    )
    if not f_peda.passed:
        return StepFeedback(stage="pedagogy", render=f_render, interact=f_interact, pedagogy=f_peda)

    return StepFeedback(stage="pass", render=f_render, interact=f_interact, pedagogy=f_peda)


# ─────────────────────────── pure helpers (testable) ───────────────────────────

Memory = List[Tuple[Dict[str, str], StepFeedback]]  # (fragments, feedback)


def _score(fb: StepFeedback, key: str) -> float:
    v = fb.scores.get(key)
    return -1.0 if v is None else v


def select_best(memory: Memory) -> int:
    """Index of best step: peda → interact → render → recency (design §6.2)."""
    best_i = 0
    best_key = None
    for i, (_frag, fb) in enumerate(memory):
        key = (_score(fb, "peda"), _score(fb, "interact"), _score(fb, "render"), i)
        if best_key is None or key >= best_key:
            best_key, best_i = key, i
    return best_i


def consecutive_render_failures(memory: Memory) -> int:
    n = 0
    for _frag, fb in reversed(memory):
        if fb.stage == "render":
            n += 1
        else:
            break
    return n


# ─────────────────────────── loop ───────────────────────────


def qa_loop(
    spec: KnowlingSpec,
    kp,
    fragments: List[str],
    providers: Dict[str, LLMProvider],
    cfg: QAConfig,
    grounding: Optional[List[Any]] = None,
    emit: EventSink = _noop,
    model_trace: Optional[list] = None,
    compile_mode: str = "template",
) -> Tuple[str, QAReport, List[str]]:
    """Returns (best_html, QAReport, best_fragments)."""
    sandbox = get_sandbox(cfg.sandbox_name)
    emit("qa", {"name": "sandbox", "backend": sandbox.name})

    block_ids = [b.block_id for b in spec.blocks]
    frag_map: Dict[str, str] = {bid: f for bid, f in zip(block_ids, fragments)}
    title = getattr(kp, "title", spec.knowledge_point_id)

    def assemble(fm: Dict[str, str]) -> str:
        return assemble_html(spec, [fm[b.block_id] for b in spec.blocks], title)

    memory: Memory = []
    compiler = providers["compile"]

    for step in range(cfg.max_qa_steps):
        html = assemble(frag_map)
        fb = qa_step(html, spec, kp, providers, sandbox, cfg, grounding)
        memory.append((dict(frag_map), fb))
        emit("qa", {"name": "step", "i": step + 1, "stage": fb.stage, "scores": fb.scores})

        if fb.all_pass():
            emit("qa", {"name": "pass", "step": step + 1})
            break

        # backtrack on repeated render errors
        if consecutive_render_failures(memory) >= cfg.backtrack_after_render_errors:
            bi = select_best(memory)
            frag_map = dict(memory[bi][0])
            emit("qa", {"name": "backtrack", "to_step": bi + 1})
            continue

        # recompile only the failed blocks (fall back to all if unlocated)
        targets = fb.failed_block_ids or block_ids
        suggestions = fb.suggestions
        emit("qa", {"name": "recompile", "blocks": targets, "stage": fb.stage})
        changed = False
        for bid in targets:
            bspec = next((b for b in spec.blocks if b.block_id == bid), None)
            if bspec is None:
                continue
            try:
                new_html, call = block_compiler.compile(
                    bspec, kp, grounding, compiler, suggestions=suggestions, mode=compile_mode
                )
                if new_html != frag_map.get(bid):
                    changed = True
                frag_map[bid] = new_html
                if model_trace is not None:
                    model_trace.append(call)
            except Exception as e:
                emit("warn", {"stage": "qa_recompile", "block_id": bid, "error": str(e)})
        # template mode (and any deterministic recompile) can't improve a block by
        # re-rendering it — if nothing changed, further steps are wasted.
        if not changed:
            emit("qa", {"name": "no_change", "step": step + 1})
            break

    best_i = select_best(memory)
    best_frag, best_fb = memory[best_i]
    best_html = assemble(best_frag)
    report = QAReport(
        score_render=best_fb.scores.get("render"),
        score_interact=best_fb.scores.get("interact"),
        score_peda=best_fb.scores.get("peda"),
        passed=best_fb.all_pass(),
        notes=([f"selected step {best_i + 1}/{len(memory)}"]
               + (best_fb.suggestions if not best_fb.all_pass() else [])),
    )
    sandbox.close()
    emit("qa", {"name": "done", "passed": report.passed, "report": report.to_dict()})
    return best_html, report, [best_frag[b.block_id] for b in spec.blocks]
