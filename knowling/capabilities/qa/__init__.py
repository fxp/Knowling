"""QA loop (design §6) — the four-dimensional quality gate.

Render (cheap VLM) → Interact (GUI agent) → Pedagogy (judge LLM) → Learnability
(learner simulation), with backtrack + select-best (WebGen-Agent). Learnability is
the final gate: a learner who already masters every prerequisite must be able to
acquire the point's knowledge from the card alone.

Runs fully offline via heuristics when providers are mock / no screenshot is
available; uses real GLM-VLM / judge + Playwright otherwise.
"""

from .types import DimensionFeedback, StepFeedback, QAConfig
from .loop import qa_loop, qa_step

__all__ = ["DimensionFeedback", "StepFeedback", "QAConfig", "qa_loop", "qa_step"]
