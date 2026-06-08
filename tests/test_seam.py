"""Phase-0 seam contract tests (docs/seam-contract-draft.md), offline (mock).

Covers: ① Curriculum coordinates, ② MasteryResult/QuizOutcome, ③ reteach
adapter, ④ the ``knowling:quiz-result`` event baked into the self-contained card.
"""

import pytest

from knowling.blocks import quiz
from knowling.capabilities import refine
from knowling.capabilities.qa import QAConfig
from knowling.engine import Config, generate_knowling, reteach_knowling
from knowling.schema import (
    Curriculum,
    KnowledgePoint,
    MasteryResult,
    QuizOutcome,
)
from knowling.schema.mastery import GREEN, RED, YELLOW, level_for


def _cfg(qa=False):
    return Config(provider_name="mock", quiet=True, qa_enabled=qa,
                  qa=QAConfig(sandbox_name="static"))


def _kp(curriculum=None):
    return KnowledgePoint(id="math.linear.slope", title="一次函数的斜率含义",
                          description="斜率 k 表示直线的倾斜程度", difficulty="core",
                          audience="初中生", curriculum=curriculum)


# ─────────────────────────── ① Curriculum ───────────────────────────


def test_curriculum_round_trips_through_kp():
    cur = Curriculum(syllabus_id="cn-pep-math-junior", grade="初二",
                     chapter="第3章 一次函数", section="3.2 图象", node_code="8.3.2")
    kp = _kp(curriculum=cur)
    d = kp.to_dict()
    assert d["curriculum"]["node_code"] == "8.3.2"
    back = KnowledgePoint.from_dict(d)
    assert back.curriculum is not None
    assert back.curriculum.syllabus_id == "cn-pep-math-junior"
    assert back.curriculum.grade == "初二"


def test_kp_without_curriculum_stays_backward_compatible():
    kp = _kp()
    assert kp.curriculum is None
    assert "curriculum" not in kp.to_dict()  # _strip_none drops it
    assert KnowledgePoint.from_dict(kp.to_dict()).curriculum is None


# ─────────────────────────── ② MasteryResult ───────────────────────────


def test_level_thresholds():
    assert level_for(1.0) == GREEN
    assert level_for(0.8) == GREEN
    assert level_for(0.6) == YELLOW
    assert level_for(0.2) == RED


def test_quiz_outcome_computes_score():
    q = QuizOutcome(total=5, correct=4)
    assert q.score == pytest.approx(0.8)
    assert QuizOutcome.from_dict({"total": 4, "correct": 1}).score == pytest.approx(0.25)


def test_mastery_from_quiz_passed_and_level():
    passed = MasteryResult.from_quiz("math.linear.slope", QuizOutcome(total=5, correct=5),
                                     knowling_id="k1")
    assert passed.passed and passed.level == GREEN
    failed = MasteryResult.from_quiz("math.linear.slope", QuizOutcome(total=5, correct=2))
    assert not failed.passed and failed.level == RED
    # round-trips
    assert MasteryResult.from_dict(passed.to_dict()).passed is True


# ─────────────────────────── ③ reteach ───────────────────────────


def test_reteach_instruction_mentions_score_and_asks_easier():
    outcome = QuizOutcome(total=4, correct=1,
                          per_question=[{"q_id": "q0", "correct": False}],
                          wrong_tags=["斜率符号"])
    instr = refine.quiz_reteach_instruction(outcome)
    assert "1/4" in instr
    assert "更易懂" in instr or "降低难度" in instr
    assert "斜率符号" in instr


def test_reteach_instruction_unwraps_mastery_result():
    mr = MasteryResult.from_quiz("k", QuizOutcome(total=3, correct=0))
    instr = refine.quiz_reteach_instruction(mr)
    assert "0/3" in instr


def test_reteach_instruction_accepts_raw_event_payload():
    payload = {"total": 5, "correct": 2, "per_question": [{"q_id": "q1", "correct": False}]}
    assert "2/5" in refine.quiz_reteach_instruction(payload)


def test_reteach_produces_a_new_card_offline():
    cfg, kp = _cfg(), _kp()
    base = generate_knowling(kp, cfg)
    outcome = QuizOutcome(total=5, correct=1)
    new, summary = reteach_knowling(base.spec, kp, outcome, cfg)
    assert new._html and "kl-card" in new._html
    assert new.spec.knowledge_point_id == base.spec.knowledge_point_id  # same KP
    assert summary


# ─────────────────────────── ④ quiz-result event ───────────────────────────


def _quiz_block(many=False):
    if many:
        cs = {"questions": [
            {"type": "single", "prompt": "斜率正负？", "options": ["正", "负"], "answer": 0},
            {"type": "fill", "prompt": "k=?", "answer": "2"},
        ]}
    else:
        cs = {"question": "斜率表示什么？", "options": ["倾斜程度", "截距"], "answer": 0}
    return {"block_id": "qz", "type": "quiz", "content_spec": cs}


def test_quiz_template_dispatches_result_event():
    html = quiz.template(_quiz_block(many=True))
    assert "knowling:quiz-result" in html
    assert "postMessage" in html
    assert "per_question" in html
    assert "window.__KNOWLING__" in html


def test_single_question_quiz_also_emits():
    # emit() must be reachable for the single-question path (else emit()).
    html = quiz.template(_quiz_block(many=False))
    assert "else emit();" in html


def test_assembler_injects_kp_identity():
    cfg = _cfg()
    cur = Curriculum(syllabus_id="cn-pep-math-junior", grade="初二", chapter="第3章")
    k = generate_knowling(_kp(curriculum=cur), cfg)
    assert "window.__KNOWLING__" in k._html
    assert "math.linear.slope" in k._html  # kp_id baked in
