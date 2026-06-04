"""QA loop (design §6) — the three-dimensional quality gate.

Render (cheap VLM) → Interact (GUI agent) → Pedagogy (judge LLM), with
backtrack + select-best (WebGen-Agent), extended with the pedagogy dimension.

Runs fully offline via heuristics when providers are mock / no screenshot is
available; uses real GLM-VLM / judge + Playwright otherwise.
"""

from .types import DimensionFeedback, StepFeedback, QAConfig
from .loop import qa_loop, qa_step

__all__ = ["DimensionFeedback", "StepFeedback", "QAConfig", "qa_loop", "qa_step"]
