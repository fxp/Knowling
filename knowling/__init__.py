"""Knowling — knowledge-point → self-contained interactive learning component.

P0 skeleton: the minimal closed loop ``KnowledgePoint → KnowlingSpec → Block[]
→ self-contained artifact``. QA loop, RAG, decompose and the full 13-block set
arrive in later phases (see knowling-design.md §12).
"""

__version__ = "0.1.0"

from .engine import generate_knowling  # noqa: E402,F401
