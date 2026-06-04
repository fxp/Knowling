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
from .capabilities import block_compiler, spec_planner
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
    # P1+: qa thresholds etc.
    approval_cb: Optional[Callable[[KnowlingSpec], KnowlingSpec]] = None
    _planner_provider: Optional[LLMProvider] = None
    _compiler_provider: Optional[LLMProvider] = None

    def planner_provider(self) -> LLMProvider:
        if self._planner_provider is None:
            self._planner_provider = get_provider(
                self.provider_name, role="plan", model=self.model, quiet=self.quiet
            )
        return self._planner_provider

    def compiler_provider(self) -> LLMProvider:
        if self._compiler_provider is None:
            # reuse planner provider if same binding (keeps mock fallback aligned)
            self._compiler_provider = get_provider(
                self.provider_name, role="compile", model=self.model, quiet=True
            )
        return self._compiler_provider


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────── stages ───────────────────────────


def plan_spec(
    kp: KnowledgePoint, cfg: Config, emit: EventSink = _noop_sink
) -> "tuple[KnowlingSpec, ModelCall]":
    """Stage ② — produce the blueprint (no code)."""
    emit("stage", {"stage": "plan", "status": "start", "kp": kp.id})
    provider = cfg.planner_provider()
    spec, call = spec_planner.plan(kp, None, provider, render_target=cfg.render_target)
    emit("cost", {"stage": "plan", **call.to_dict()})
    emit(
        "stage",
        {"stage": "plan", "status": "done", "blocks": [b.type for b in spec.blocks]},
    )
    return spec, call


def approval_gate(spec: KnowlingSpec, cfg: Config, emit: EventSink = _noop_sink) -> KnowlingSpec:
    """Stage ②.5 — auto-approve by default; human/cb hook for high-risk."""
    emit("stage", {"stage": "approve", "status": "start", "mode": cfg.approval})
    if cfg.approval == "human" and cfg.approval_cb is not None:
        spec = cfg.approval_cb(spec)
    emit("stage", {"stage": "approve", "status": "done"})
    return spec


def compile_blocks(
    spec: KnowlingSpec, kp: KnowledgePoint, cfg: Config, emit: EventSink = _noop_sink
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
            html, call = block_compiler.compile(b, kp, None, provider)
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
    # P0 has no QA loop → status is "draft" (not "ready"; design §3.1 #2).
    knowling = Knowling(
        id=f"knowling.{kp.id}",
        knowledge_point_id=kp.id,
        spec=spec,
        artifact=artifact,
        qa=QAReport(passed=False, notes=["P0: QA loop not yet run"]),
        graph_links=GraphLinks(prerequisites=kp.prerequisites, followups=kp.followups),
        status="draft",
        created_at=_now(),
        model_trace=model_trace,
    )
    # stash the rendered html so callers that didn't pass out_path can still use it
    knowling._html = html  # type: ignore[attr-defined]
    emit("stage", {"stage": "assemble", "status": "done", "entry": entry})
    return knowling


# ─────────────────────────── orchestrator ───────────────────────────


def generate_knowling(
    kp: KnowledgePoint,
    cfg: Optional[Config] = None,
    out_path: Optional[str] = None,
    emit: EventSink = _noop_sink,
) -> Knowling:
    """Full P0 pipeline: Plan → Approve → Compile → Assemble."""
    cfg = cfg or Config()
    emit("info", {"msg": "generate_knowling start", "kp": kp.id, "provider": cfg.provider_name})

    spec, plan_call = plan_spec(kp, cfg, emit)
    spec = approval_gate(spec, cfg, emit)
    fragments, compile_calls = compile_blocks(spec, kp, cfg, emit)
    trace = [plan_call] + compile_calls
    knowling = finalize(spec, kp, fragments, trace, cfg, out_path=out_path, emit=emit)

    total_cost = round(sum(c.cost_usd for c in trace), 6)
    emit("done", {"id": knowling.id, "status": knowling.status, "cost_usd": total_cost,
                  "entry": knowling.artifact.entry})
    return knowling
