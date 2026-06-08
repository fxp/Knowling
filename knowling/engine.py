"""L3 orchestration (design §3.2, §5) — the ``generate_knowling`` pipeline.

P0 implements stages ② Plan → ②.5 Approval (auto) → ④ Compile → ⑥ Assemble.
① Decompose, ③ Retrieve and ⑤ QA-loop are stubbed/skipped and arrive in later
phases. Every stage emits a progress event so the CLI can stream rich/JSON.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from . import blocks as block_registry
from .assembler import assemble_html
from .capabilities import (
    block_compiler,
    fidelity as fidelity_mod,
    refine as refine_mod,
    retriever as retriever_mod,
    spec_planner,
)
from .capabilities.qa import QAConfig, qa_loop
from .providers import LLMProvider, get_provider
from .schema import (
    Artifact,
    GraphLinks,
    KnowledgePoint,
    Knowling,
    KnowlingSpec,
    ModelCall,
    QAReport,
)

# event(kind, payload) — kind ∈ {stage, info, cost, warn, error, done}
EventSink = Callable[[str, dict], None]


def _noop_sink(kind: str, payload: dict) -> None:
    return None


@dataclass
class Config:
    provider_name: str = "auto"
    model: Optional[str] = None
    render_target: str = "html"
    approval: str = "auto"  # "auto" | "human"
    quiet: bool = False
    retriever_name: str = "auto"  # P2: RAG grounding backend
    compile_mode: str = "template"  # "template" (consistent) | "codegen" (bespoke)
    qa_enabled: bool = True  # P1: run the three-dimensional QA loop
    qa: QAConfig = field(default_factory=QAConfig)
    approval_cb: Optional[Callable[[KnowlingSpec], KnowlingSpec]] = None
    _providers: dict = field(default_factory=dict)

    def provider(self, role: str) -> LLMProvider:
        """Cached per-role provider (cost separation, design §6.3)."""
        if role not in self._providers:
            # model override only applies to plan/compile; QA roles use defaults
            mdl = self.model if role in ("plan", "compile") else None
            self._providers[role] = get_provider(
                self.provider_name, role=role, model=mdl,
                quiet=(self.quiet or role != "plan"),
            )
        return self._providers[role]

    # back-compat accessors
    def planner_provider(self) -> LLMProvider:
        return self.provider("plan")

    def compiler_provider(self) -> LLMProvider:
        return self.provider("compile")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────── stages ───────────────────────────


def plan_spec(
    kp: KnowledgePoint, cfg: Config, emit: EventSink = _noop_sink, grounding=None
) -> "tuple[KnowlingSpec, ModelCall]":
    """Stage ② — produce the blueprint (no code)."""
    emit("stage", {"stage": "plan", "status": "start", "kp": kp.id})
    provider = cfg.planner_provider()
    spec, call = spec_planner.plan(kp, grounding, provider, render_target=cfg.render_target)
    emit("cost", {"stage": "plan", **call.to_dict()})
    emit(
        "stage",
        {"stage": "plan", "status": "done", "blocks": [b.type for b in spec.blocks]},
    )
    return spec, call


def retrieve(kp: KnowledgePoint, cfg: Config, emit: EventSink = _noop_sink):
    """Stage ③ — optional RAG grounding from kp.source_refs (design §5 ③)."""
    if not kp.source_refs:
        return None
    emit("stage", {"stage": "retrieve", "status": "start", "refs": len(kp.source_refs)})
    r = retriever_mod.get_retriever(cfg.retriever_name)
    query = f"{kp.title} {kp.description}"
    chunks = r.fetch(kp.source_refs, query=query)
    emit("stage", {"stage": "retrieve", "status": "done", "chunks": len(chunks)})
    return chunks or None


def approval_gate(spec: KnowlingSpec, cfg: Config, emit: EventSink = _noop_sink) -> KnowlingSpec:
    """Stage ②.5 — auto-approve by default; human/cb hook for high-risk."""
    emit("stage", {"stage": "approve", "status": "start", "mode": cfg.approval})
    if cfg.approval == "human" and cfg.approval_cb is not None:
        spec = cfg.approval_cb(spec)
    emit("stage", {"stage": "approve", "status": "done"})
    return spec


def compile_blocks(
    spec: KnowlingSpec, kp: KnowledgePoint, cfg: Config, emit: EventSink = _noop_sink,
    grounding=None,
) -> "tuple[List[str], List[ModelCall]]":
    """Stage ④ — compile each block to a self-contained fragment."""
    provider = cfg.compiler_provider()
    fragments: List[str] = []
    calls: List[ModelCall] = []
    for i, b in enumerate(spec.blocks):
        emit(
            "stage",
            {"stage": "compile", "status": "start", "block_id": b.block_id, "type": b.type,
             "i": i + 1, "n": len(spec.blocks)},
        )
        try:
            html, call = block_compiler.compile(b, kp, grounding, provider, mode=cfg.compile_mode)
        except Exception as e:  # block-level failure shouldn't kill the run in P0
            emit("warn", {"stage": "compile", "block_id": b.block_id, "error": str(e)})
            html = block_registry.render_block_template(b.to_dict())
            call = ModelCall(stage="compile", provider=provider.name, model=getattr(provider, "model", "?"))
        fragments.append(html)
        calls.append(call)
        emit("cost", {"stage": "compile", "block_id": b.block_id, **call.to_dict()})
        emit("stage", {"stage": "compile", "status": "done", "block_id": b.block_id})
    return fragments, calls


def finalize(
    spec: KnowlingSpec,
    kp: KnowledgePoint,
    fragments: List[str],
    model_trace: List[ModelCall],
    cfg: Config,
    out_path: Optional[str] = None,
    emit: EventSink = _noop_sink,
    qa_report: Optional[QAReport] = None,
    status: str = "draft",
) -> Knowling:
    """Stage ⑥ — assemble artifact, build graph links, finalize record."""
    emit("stage", {"stage": "assemble", "status": "start"})
    html = assemble_html(spec, fragments, kp.title)

    entry = out_path or ""
    if out_path:
        import os

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        entry = out_path

    artifact = Artifact(format=spec.render_target, entry=entry, self_contained=True)
    if qa_report is None:
        # QA skipped → never "ready" (design §3.1 #2)
        qa_report = QAReport(passed=False, notes=["QA loop skipped"])
        status = "draft"
    knowling = Knowling(
        id=f"knowling.{kp.id}",
        knowledge_point_id=kp.id,
        spec=spec,
        artifact=artifact,
        qa=qa_report,
        graph_links=GraphLinks(prerequisites=kp.prerequisites, followups=kp.followups),
        status=status,
        created_at=_now(),
        model_trace=model_trace,
    )
    # stash the rendered html so callers that didn't pass out_path can still use it
    knowling._html = html  # type: ignore[attr-defined]
    emit("stage", {"stage": "assemble", "status": "done", "entry": entry})
    return knowling


# ─────────────────────────── orchestrator ───────────────────────────


def compile_spec(
    spec: KnowlingSpec,
    kp: KnowledgePoint,
    cfg: Config,
    out_path: Optional[str] = None,
    emit: EventSink = _noop_sink,
    base_trace: Optional[List[ModelCall]] = None,
    grounding=None,
) -> Knowling:
    """Stages ④ Compile → ⑤ QA → ⑥ Assemble (shared by gen and compile)."""
    trace = list(base_trace or [])
    fragments, compile_calls = compile_blocks(spec, kp, cfg, emit, grounding=grounding)
    trace += compile_calls

    qa_report: Optional[QAReport] = None
    status = "draft"
    if cfg.qa_enabled:
        emit("stage", {"stage": "qa", "status": "start"})
        providers = {
            "compile": cfg.provider("compile"),
            "render": cfg.provider("render_vlm"),
            "gui": cfg.provider("gui"),
            "judge": cfg.provider("judge"),
        }
        best_html, qa_report, fragments = qa_loop(
            spec, kp, fragments, providers, cfg.qa, grounding=grounding,
            emit=emit, model_trace=trace, compile_mode=cfg.compile_mode,
        )
        status = "ready" if qa_report.passed else "qa_failed"
        emit("stage", {"stage": "qa", "status": "done", "passed": qa_report.passed,
                       "ready": status == "ready"})

    knowling = finalize(spec, kp, fragments, trace, cfg, out_path=out_path, emit=emit,
                        qa_report=qa_report, status=status)

    total_cost = round(sum(c.cost_usd for c in trace), 6)
    emit("done", {"id": knowling.id, "status": knowling.status, "cost_usd": total_cost,
                  "entry": knowling.artifact.entry, "qa": knowling.qa.to_dict()})
    return knowling


def generate_knowling(
    kp: KnowledgePoint,
    cfg: Optional[Config] = None,
    out_path: Optional[str] = None,
    emit: EventSink = _noop_sink,
) -> Knowling:
    """Full pipeline: Plan → Approve → Compile → QA → Assemble."""
    cfg = cfg or Config()
    emit("info", {"msg": "generate_knowling start", "kp": kp.id, "provider": cfg.provider_name})
    grounding = retrieve(kp, cfg, emit)
    spec, plan_call = plan_spec(kp, cfg, emit, grounding=grounding)
    spec = approval_gate(spec, cfg, emit)
    return compile_spec(spec, kp, cfg, out_path=out_path, emit=emit,
                        base_trace=[plan_call], grounding=grounding)


def refine_knowling(
    spec: KnowlingSpec,
    kp: KnowledgePoint,
    instruction: str,
    cfg: Optional[Config] = None,
    out_path: Optional[str] = None,
    emit: EventSink = _noop_sink,
) -> "tuple[Knowling, str]":
    """Chat-driven: current card spec + user instruction → a NEW card.

    The card itself is a fixed state; this turns one fixed state into the next.
    Returns (new_knowling, summary-of-changes).
    """
    cfg = cfg or Config()
    emit("stage", {"stage": "refine", "status": "start", "instruction": instruction})
    provider = cfg.provider("plan")
    judge = cfg.provider("judge")
    trace = []

    new_spec, call, summary, changes = refine_mod.refine(spec, kp, instruction, provider)
    trace.append(call)

    # fidelity guard: keep the card on its knowledge point (anti-drift)
    fid = fidelity_mod.assess(new_spec, kp, judge)
    emit("stage", {"stage": "fidelity", "status": "check", **fid.to_dict()})
    if not fid.ok:
        emit("stage", {"stage": "fidelity", "status": "reanchor", "reason": fid.reason})
        reinforced = instruction + "（务必始终聚焦讲解本知识点本身，不要跑题成讲别的主题）"
        spec2, call2, summary2, changes2 = refine_mod.refine(spec, kp, reinforced, provider)
        trace.append(call2)
        fid2 = fidelity_mod.assess(spec2, kp, judge)
        if fid2.ok or fid2.score >= fid.score:
            new_spec, summary, changes, fid = spec2, summary2, changes2, fid2
        if not fid.ok:
            summary += "（已尽量保持聚焦本知识点）"

    # deterministic block-type delta, appended to the model's change list
    delta = refine_mod.block_delta(spec, new_spec)
    changes = list(changes) + [f"📦 {delta}"]

    emit("stage", {"stage": "refine", "status": "done", "summary": summary,
                   "changes": changes, "fidelity": fid.to_dict(),
                   "blocks": [b.type for b in new_spec.blocks]})
    knowling = compile_spec(new_spec, kp, cfg, out_path=out_path, emit=emit, base_trace=trace)
    knowling._fidelity = fid.to_dict()  # type: ignore[attr-defined]
    knowling._changes = changes  # type: ignore[attr-defined]
    return knowling, summary, changes


def reteach_knowling(
    spec: KnowlingSpec,
    kp: KnowledgePoint,
    outcome: Any,
    cfg: Optional[Config] = None,
    out_path: Optional[str] = None,
    emit: EventSink = _noop_sink,
) -> "tuple[Knowling, str]":
    """Seam ③ — signal-driven re-teach: a failed quiz result → an easier card for
    the SAME kp. A thin adapter over ``refine_knowling`` (the quiz failure is
    translated into a refine instruction). Single round; the caller (an L2 session
    runner) loops ``reteach → re-test`` until the learner passes.

    ``outcome`` is a ``QuizOutcome``/``MasteryResult`` or the raw
    ``knowling:quiz-result`` event payload dict. Returns (new_knowling, summary).
    """
    instruction = refine_mod.quiz_reteach_instruction(outcome)
    emit("stage", {"stage": "reteach", "status": "start",
                   "kp": getattr(kp, "id", ""), "instruction": instruction})
    knowling, summary, _changes = refine_knowling(
        spec, kp, instruction, cfg=cfg, out_path=out_path, emit=emit)
    return knowling, summary
