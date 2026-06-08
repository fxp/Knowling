"""Mastery signal (seam contract ②, see docs/seam-contract-draft.md).

What a Knowling learning unit (L3) reports to a host orchestrator (L1) after the
learner finishes the quiz. Single-KP only: this is *one* knowledge point's
observed result.

Responsibility boundary: the "monotone non-decreasing" rule (a learner only
progresses, never regresses) is enforced by the host state layer, NOT here —
Knowling reports the current observation; the host does ``max(history, observed)``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

GREEN, YELLOW, RED = "green", "yellow", "red"


def level_for(score: float, *, green: float = 0.8, yellow: float = 0.5) -> str:
    """Map a 0..1 score to a red/yellow/green light (graph lighting + strength)."""
    if score >= green:
        return GREEN
    if score >= yellow:
        return YELLOW
    return RED


@dataclass
class AxisScore:
    """Optional four-axis refinement (adapted from get-it). Each 0..1."""

    memory: float = 0.0
    comprehension: float = 0.0
    structure: float = 0.0
    application: float = 0.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AxisScore":
        return cls(**{k: float(d.get(k, 0.0))
                      for k in ("memory", "comprehension", "structure", "application")})

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class QuizOutcome:
    """The raw quiz result — mirrors the ``knowling:quiz-result`` event payload
    the self-contained card dispatches (seam contract ④)."""

    total: int
    correct: int
    score: float = 0.0  # correct / total
    per_question: List[Dict[str, Any]] = field(default_factory=list)
    wrong_tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.score and self.total:
            self.score = self.correct / self.total

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "QuizOutcome":
        total = int(d.get("total", 0))
        correct = int(d.get("correct", 0))
        return cls(
            total=total,
            correct=correct,
            score=float(d.get("score", (correct / total) if total else 0.0)),
            per_question=list(d.get("per_question", [])),
            wrong_tags=[str(t) for t in d.get("wrong_tags", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "correct": self.correct,
            "score": self.score,
            "per_question": self.per_question,
            "wrong_tags": self.wrong_tags,
        }


@dataclass
class MasteryResult:
    """The structured signal L3 emits → L1 lights the graph node."""

    kp_id: str
    knowling_id: str = ""
    quiz: Optional[QuizOutcome] = None
    score: float = 0.0
    passed: bool = False
    level: str = RED
    attempts: int = 1
    axes: Optional[AxisScore] = None
    reasons: List[str] = field(default_factory=list)
    observed_at: str = ""

    @classmethod
    def from_quiz(
        cls,
        kp_id: str,
        quiz: QuizOutcome,
        *,
        knowling_id: str = "",
        pass_threshold: float = 0.8,
        attempts: int = 1,
        axes: Optional[AxisScore] = None,
        reasons: Optional[List[str]] = None,
        observed_at: str = "",
    ) -> "MasteryResult":
        score = quiz.score
        return cls(
            kp_id=kp_id,
            knowling_id=knowling_id,
            quiz=quiz,
            score=score,
            passed=score >= pass_threshold,
            level=level_for(score),
            attempts=attempts,
            axes=axes,
            reasons=list(reasons or []),
            observed_at=observed_at,
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MasteryResult":
        return cls(
            kp_id=d.get("kp_id", ""),
            knowling_id=d.get("knowling_id", ""),
            quiz=QuizOutcome.from_dict(d["quiz"]) if d.get("quiz") else None,
            score=float(d.get("score", 0.0)),
            passed=bool(d.get("passed", False)),
            level=d.get("level", RED),
            attempts=int(d.get("attempts", 1)),
            axes=AxisScore.from_dict(d["axes"]) if d.get("axes") else None,
            reasons=[str(r) for r in d.get("reasons", [])],
            observed_at=d.get("observed_at", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "kp_id": self.kp_id,
            "knowling_id": self.knowling_id,
            "score": self.score,
            "passed": self.passed,
            "level": self.level,
            "attempts": self.attempts,
            "reasons": self.reasons,
            "observed_at": self.observed_at,
        }
        if self.quiz is not None:
            out["quiz"] = self.quiz.to_dict()
        if self.axes is not None:
            out["axes"] = self.axes.to_dict()
        return out
