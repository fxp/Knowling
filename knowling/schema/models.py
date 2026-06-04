"""Dataclass models for the Knowling pipeline (knowling-design.md §4).

Design notes baked in here:
  * ``KnowlingSpec`` is the *only* human-reviewable / diffable layer (the
    approval gate, D2). It is pure structure — no rendered code.
  * Block content lives in ``BlockSpec.content_spec`` as a free-form dict so
    each block type owns its own schema (validated in ``knowling.blocks``).
  * Everything round-trips to/from plain dicts → JSON for the CLI's ``-f json``
    event stream and for ``knowling plan``/``compile`` interchange.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# BlockType — P0 implements text / quiz / param_sim; the rest are declared so
# specs validate and later phases can light them up (design §4.3, §7).
BLOCK_TYPES = (
    "text", "callout", "figure", "code", "section",
    "quiz", "flashcards",
    "timeline", "concept_graph",
    "interactive_demo", "param_sim", "step_through", "animation",
    "deep_dive", "user_note",
)
BlockType = str  # constrained at validation time, kept as str for JSON ease.

DIFFICULTIES = ("intro", "core", "advanced")
RENDER_TARGETS = ("react", "html")
STATUSES = ("draft", "qa_failed", "ready")


def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
    """Drop None / empty-list keys so serialized specs stay terse and diffable."""
    return {k: v for k, v in d.items() if v is not None and v != [] and v != {}}


@dataclass
class SourceRef:
    """A grounding reference (RAG / uploaded material). P0: metadata only."""

    id: str
    title: Optional[str] = None
    uri: Optional[str] = None
    snippet: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SourceRef":
        return cls(**{k: d.get(k) for k in ("id", "title", "uri", "snippet")})

    def to_dict(self) -> Dict[str, Any]:
        return _strip_none(dataclasses.asdict(self))


# ─────────────────────────────── input ───────────────────────────────


@dataclass
class KnowledgePoint:
    """Pipeline input (design §4.1). ``description`` should be as specific as
    possible — it scopes everything downstream."""

    id: str
    title: str
    description: str = ""
    learning_objectives: List[str] = field(default_factory=list)
    difficulty: str = "core"
    prerequisites: List[str] = field(default_factory=list)
    followups: List[str] = field(default_factory=list)
    audience: Optional[str] = None
    source_refs: List[SourceRef] = field(default_factory=list)
    locale: str = "zh-CN"

    def __post_init__(self) -> None:
        if self.difficulty not in DIFFICULTIES:
            raise ValueError(
                f"difficulty must be one of {DIFFICULTIES}, got {self.difficulty!r}"
            )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowledgePoint":
        return cls(
            id=d["id"],
            title=d["title"],
            description=d.get("description", ""),
            learning_objectives=list(d.get("learning_objectives", [])),
            difficulty=d.get("difficulty", "core"),
            prerequisites=list(d.get("prerequisites", [])),
            followups=list(d.get("followups", [])),
            audience=d.get("audience"),
            source_refs=[SourceRef.from_dict(s) for s in d.get("source_refs", [])],
            locale=d.get("locale", "zh-CN"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return _strip_none(
            {
                "id": self.id,
                "title": self.title,
                "description": self.description,
                "learning_objectives": self.learning_objectives,
                "difficulty": self.difficulty,
                "prerequisites": self.prerequisites,
                "followups": self.followups,
                "audience": self.audience,
                "source_refs": [s.to_dict() for s in self.source_refs],
                "locale": self.locale,
            }
        )


# ─────────────────────────────── spec (blueprint) ───────────────────────────────


@dataclass
class Pedagogy:
    """The teaching frame — drives the pedagogy QA dimension in later phases."""

    hook: str = ""
    central_phenomenon: str = ""
    misconceptions: List[str] = field(default_factory=list)
    aha_moment: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Pedagogy":
        return cls(
            hook=d.get("hook", ""),
            central_phenomenon=d.get("central_phenomenon", ""),
            misconceptions=list(d.get("misconceptions", [])),
            aha_moment=d.get("aha_moment", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook": self.hook,
            "central_phenomenon": self.central_phenomenon,
            "misconceptions": self.misconceptions,
            "aha_moment": self.aha_moment,
        }


@dataclass
class BlockSpec:
    """One block's blueprint (design §4.2). ``content_spec`` is block-specific."""

    block_id: str
    type: BlockType
    intent: str = ""
    content_spec: Dict[str, Any] = field(default_factory=dict)
    interaction_spec: Optional[Dict[str, Any]] = None
    grounding: List[SourceRef] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.type not in BLOCK_TYPES:
            raise ValueError(f"unknown block type {self.type!r}; one of {BLOCK_TYPES}")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BlockSpec":
        return cls(
            block_id=d["block_id"],
            type=d["type"],
            intent=d.get("intent", ""),
            content_spec=dict(d.get("content_spec", {})),
            interaction_spec=d.get("interaction_spec"),
            grounding=[SourceRef.from_dict(s) for s in d.get("grounding", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return _strip_none(
            {
                "block_id": self.block_id,
                "type": self.type,
                "intent": self.intent,
                "content_spec": self.content_spec,
                "interaction_spec": self.interaction_spec,
                "grounding": [s.to_dict() for s in self.grounding],
            }
        )


@dataclass
class KnowlingSpec:
    """The blueprint / approval gate (design §4.2)."""

    knowledge_point_id: str
    pedagogy: Pedagogy = field(default_factory=Pedagogy)
    blocks: List[BlockSpec] = field(default_factory=list)
    render_target: str = "html"
    est_cost_usd: Optional[float] = None
    version: int = 1

    def __post_init__(self) -> None:
        if self.render_target not in RENDER_TARGETS:
            raise ValueError(
                f"render_target must be one of {RENDER_TARGETS}, got {self.render_target!r}"
            )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowlingSpec":
        return cls(
            knowledge_point_id=d["knowledge_point_id"],
            pedagogy=Pedagogy.from_dict(d.get("pedagogy", {})),
            blocks=[BlockSpec.from_dict(b) for b in d.get("blocks", [])],
            render_target=d.get("render_target", "html"),
            est_cost_usd=d.get("est_cost_usd"),
            version=int(d.get("version", 1)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return _strip_none(
            {
                "knowledge_point_id": self.knowledge_point_id,
                "pedagogy": self.pedagogy.to_dict(),
                "blocks": [b.to_dict() for b in self.blocks],
                "render_target": self.render_target,
                "est_cost_usd": self.est_cost_usd,
                "version": self.version,
            }
        )


# ─────────────────────────────── output ───────────────────────────────


@dataclass
class Artifact:
    format: str = "html"
    entry: str = ""
    self_contained: bool = True

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Artifact":
        return cls(
            format=d.get("format", "html"),
            entry=d.get("entry", ""),
            self_contained=bool(d.get("self_contained", True)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class ModelCall:
    """One LLM/VLM call for cost & model audit (design §4.4 model_trace)."""

    stage: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class QAReport:
    """Placeholder until P1. P0 leaves this empty (no QA loop yet)."""

    score_render: Optional[float] = None
    score_interact: Optional[float] = None
    score_peda: Optional[float] = None
    passed: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _strip_none(dataclasses.asdict(self))


@dataclass
class GraphLinks:
    prerequisites: List[str] = field(default_factory=list)
    followups: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class Knowling:
    """The output product (design §4.4)."""

    id: str
    knowledge_point_id: str
    spec: KnowlingSpec
    artifact: Artifact
    qa: QAReport = field(default_factory=QAReport)
    graph_links: GraphLinks = field(default_factory=GraphLinks)
    status: str = "draft"
    created_at: str = ""
    model_trace: List[ModelCall] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "knowledge_point_id": self.knowledge_point_id,
            "spec": self.spec.to_dict(),
            "artifact": self.artifact.to_dict(),
            "qa": self.qa.to_dict(),
            "graph_links": self.graph_links.to_dict(),
            "status": self.status,
            "created_at": self.created_at,
            "model_trace": [m.to_dict() for m in self.model_trace],
        }
