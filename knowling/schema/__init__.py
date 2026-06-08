"""Core data structures — see knowling-design.md §4.

Plain dataclasses (no pydantic dep). Each carries ``from_dict`` / ``to_dict``
so specs round-trip cleanly through JSON (the approval-gate / diff surface).
"""

from .models import (
    Artifact,
    BlockSpec,
    BLOCK_TYPES,
    BlockType,
    Curriculum,
    GraphLinks,
    KnowledgePoint,
    Knowling,
    KnowlingSpec,
    ModelCall,
    Pedagogy,
    QAReport,
    SourceRef,
)
from .mastery import AxisScore, MasteryResult, QuizOutcome, level_for

__all__ = [
    "Artifact",
    "AxisScore",
    "BlockSpec",
    "BLOCK_TYPES",
    "BlockType",
    "Curriculum",
    "GraphLinks",
    "KnowledgePoint",
    "Knowling",
    "KnowlingSpec",
    "MasteryResult",
    "ModelCall",
    "Pedagogy",
    "QAReport",
    "QuizOutcome",
    "SourceRef",
    "level_for",
]
