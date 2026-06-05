"""QA feedback structures + thresholds (design §6.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class QAConfig:
    # GLM-VLM render scores and the LLM pedagogy judge are strict and have real
    # run-to-run variance; 3.0/5 from them is a solid component. Interaction is
    # deterministic (static invariant checks) so it keeps a higher bar.
    render_threshold: float = 3.0
    interact_threshold: float = 3.5
    pedagogy_threshold: float = 3.0
    max_qa_steps: int = 4
    backtrack_after_render_errors: int = 5
    sandbox_name: str = "auto"


@dataclass
class DimensionFeedback:
    """One dimension's verdict (render | interact | pedagogy)."""

    stage: str
    score: float  # 0-5
    suggestions: List[str] = field(default_factory=list)
    passed: bool = False
    description: str = ""
    failed_block_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "stage": self.stage,
            "score": round(self.score, 2),
            "passed": self.passed,
            "suggestions": self.suggestions,
            "description": self.description,
            "failed_block_ids": self.failed_block_ids,
        }


@dataclass
class StepFeedback:
    """Result of one qa_step. ``stage`` = the first dimension that failed
    (or 'pass'). Scores carry whichever dimensions were evaluated."""

    stage: str
    render: Optional[DimensionFeedback] = None
    interact: Optional[DimensionFeedback] = None
    pedagogy: Optional[DimensionFeedback] = None

    @property
    def scores(self) -> Dict[str, Optional[float]]:
        return {
            "render": self.render.score if self.render else None,
            "interact": self.interact.score if self.interact else None,
            "peda": self.pedagogy.score if self.pedagogy else None,
        }

    def all_pass(self) -> bool:
        return self.stage == "pass"

    @property
    def suggestions(self) -> List[str]:
        for dim in (self.render, self.interact, self.pedagogy):
            if dim and not dim.passed:
                return dim.suggestions
        return []

    @property
    def failed_block_ids(self) -> List[str]:
        for dim in (self.interact, self.render, self.pedagogy):
            if dim and dim.failed_block_ids:
                return dim.failed_block_ids
        return []

    def to_dict(self) -> Dict:
        return {
            "stage": self.stage,
            "scores": self.scores,
            "render": self.render.to_dict() if self.render else None,
            "interact": self.interact.to_dict() if self.interact else None,
            "pedagogy": self.pedagogy.to_dict() if self.pedagogy else None,
        }
