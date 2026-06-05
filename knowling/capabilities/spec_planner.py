"""Spec planner (design §5 ②, §10.1) — KnowledgePoint → KnowlingSpec.

Produces a structured blueprint *only* (no code). This is the approval-gate
layer. Strong LLM by default; mock provider returns a canned 3-block spec.
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

from ..providers.base import LLMProvider
from ..schema import KnowledgePoint, KnowlingSpec, ModelCall
from ._extract import extract_json

SYSTEM = "你是学习组件的教学设计师。只产出结构化蓝图（JSON），绝不写任何代码。"

PROMPT_TEMPLATE = """针对单个知识点产出 KnowlingSpec（严格 JSON），不要写任何代码。

知识点: {title} — {description}
学习目标: {objectives}
受众/难度: {audience} / {difficulty}
渲染目标: {render_target}
{grounding}

要求:
1. 先定 pedagogy: hook(抓手)、central_phenomenon(要引导注意的中心现象)、
   misconceptions(常见误解, 数组)、aha_moment(期望顿悟点)。
2. 选 ≤6 个 block 并排序。优先 param_sim/step_through/interactive_demo——
   让读者能"动手改变某个量并观察结果", 而非只读文字。
3. 每个 block 写明 block_id、type、intent(教学意图) 与 content_spec(结构化内容, 非代码)。
4. 交互块写 interaction_spec.invariants(交互后必须成立的属性, 供测试断言)。

可用 block type: text, callout, figure, code, section, quiz, flashcards,
timeline, concept_graph, interactive_demo, param_sim, step_through, animation,
deep_dive, user_note。

content_spec 约定(严格按字段名输出):
- text:     {{ "md": "markdown" }}
- quiz:     单题 {{ "question": str, "options": [str], "answer": int, "explain": str }}
            或多题 {{ "title": str, "questions": [{{"type","prompt","options"?,"answer","explain"}}] }}
            type ∈ single/multi(answer 为 int 数组)/boolean(answer 为 bool)/fill(answer 为 str)
- param_sim:{{ "params": [{{"name","label","min","max","step","default"}}],
              "outputs": [{{"name","label","expr"}}], "x_range": [min,max], "explain": str }}
  用于「拖动参数滑块, 观察 y=f(x) 曲线如何变化」。expr 是 JS 表达式, 可用 Math。
  画函数曲线时, 用自变量 x 作横轴(它不是滑块, 不要放进 params), 滑块只放参数;
  例如 params=[A,ω,φ], output expr="A*sin(ω*x+φ)", x_range=[-6.28,6.28]。
  纯标量(无 x)的 output 会显示为数值, 如周期 "2*PI/ω"。
- interactive_demo: {{ "controls": [{{"name","label","kind"}}],
              "outputs": [{{"name","label","expr"}}], "explain": str }}
  仅用于「标量关系」: expr 只能用 controls 里定义的 name, 不能出现未定义的自变量(如 x)。
  需要画 y=f(x) 曲线时请用 param_sim, 不要用 interactive_demo。
  kind ∈ slider/number/select/checkbox/text。
- step_through: {{ "steps": [{{"state","explain"}}] }}
  必须用字段名 "state"(本步状态) 与 "explain"(本步说明); 不要用 title/describe 等其它名。

输出严格符合 KnowlingSpec schema 的 JSON, 顶层字段:
knowledge_point_id, pedagogy, blocks, render_target, version。"""


def _format_objectives(kp: KnowledgePoint) -> str:
    return "；".join(kp.learning_objectives) if kp.learning_objectives else "（未指定）"


def plan(
    kp: KnowledgePoint,
    grounding: Optional[List[Any]],
    provider: LLMProvider,
    render_target: str = "html",
) -> Tuple[KnowlingSpec, ModelCall]:
    grounding_txt = ""
    if grounding:
        from .retriever import format_grounding, GroundingChunk

        if isinstance(grounding, str):
            body = grounding
        else:
            chunks = [g for g in grounding if isinstance(g, GroundingChunk)]
            body = format_grounding(chunks) if chunks else "\n".join(str(g) for g in grounding)
        if body:
            grounding_txt = "依据材料(grounding):\n" + body

    user = PROMPT_TEMPLATE.format(
        title=kp.title,
        description=kp.description or kp.title,
        objectives=_format_objectives(kp),
        audience=kp.audience or "通用",
        difficulty=kp.difficulty,
        render_target=render_target,
        grounding=grounding_txt,
    )
    comp = provider.complete(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        task="plan",
        temperature=0.5,
        max_tokens=8000,
        thinking="disabled",
        meta={"kp": kp.to_dict()},
    )
    data = extract_json(comp.text)
    if not isinstance(data, dict):
        raise ValueError(
            "spec planner did not return valid JSON. Raw head:\n"
            + comp.text[:400]
        )
    data.setdefault("knowledge_point_id", kp.id)
    data.setdefault("render_target", render_target)
    spec = KnowlingSpec.from_dict(data)

    call = ModelCall(
        stage="plan",
        provider=comp.provider,
        model=comp.model,
        prompt_tokens=comp.prompt_tokens,
        completion_tokens=comp.completion_tokens,
        cost_usd=comp.cost_usd,
    )
    return spec, call
