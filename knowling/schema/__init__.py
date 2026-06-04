"""Core data structures — see knowling-design.md §4.

Plain dataclasses (no pydantic dep). Each carries ``from_dict`` / ``to_dict``
so specs round-trip cleanly through JSON (the approval-gate / diff surface).
"""

from .models import (
    Artifact,
    BlockSpec,
    BLOCK_TYPES,
    BlockType,
    GraphLinks,
    KnowledgePoint,
    Knowling,
    KnowlingSpec,
    ModelCall,
    Pedagogy,
    QAReport,
    SourceRef,
)

__all__ = [
    "Artifact",
    "BlockSpec",
    "BLOCK_TYPES",
    "BlockType",
    "GraphLinks",
    "KnowledgePoint",
    "Knowling",
    "KnowlingSpec",
    "ModelCall",
    "Pedagogy",
    "QAReport",
    "SourceRef",
]
