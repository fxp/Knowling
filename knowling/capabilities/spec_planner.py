"""Spec planner (design §5 ②, §10.1) — KnowledgePoint → KnowlingSpec.

Produces a structured blueprint *only* (no code). This is the approval-gate
layer. Strong LLM by default; mock provider returns a canned 3-block spec.
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

from ..providers.base import LLMProvider
from ..schema import KnowledgePoint, KnowlingSpec, ModelCall
from ._extract import complete_json, extract_json

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
2. 选 4-6 个 block 并排序。**核心要求: 尽量让每一页都带多媒体(可视 / 可交互 /
   可听), 尽量减少纯文字页。** 一张卡**必须至少包含一个可视化或可交互块**
   (param_sim / interactive_demo / animation / concept_graph / step_through);
   不要做成"几段文字 + 一道题"。按下列模态搭配(至少覆盖 3 类):
   - 启发/直觉: callout(生活类比、为什么重要、反直觉之处)
   - 理论/概念: text(讲清定义、原理、关键公式)——纯文字页尽量紧跟一个交互/可视块
   - 可视化+交互(重心, 必有): param_sim / interactive_demo(拖动看曲线/数值变化)、
     step_through(逐步推演证明或过程)、animation(过程演示)、concept_graph(关系图)
   - 听觉(仅声学场景): 当知识点真的涉及**声音**(声波/音高/响度/振动发声/音乐/节拍,
     或正弦波等可发声的周期信号)时, **务必**加一个 audio 块, 让读者拖滑块边看波形边
     "听见"变化(频率→音高, 振幅→响度)。注意: 概率/统计里的"频率"与声音无关, 不要加 audio。
   - 实例: text 或 callout(一个具体例子完整走一遍, 代入真实数字)
   - 评测: quiz(检验是否真懂, 可多题/多题型)
   **优先用可视化呈现**: 凡函数/几何/随量变化的知识点, 必须有 param_sim 的二维坐标系
   曲线; 几何/图形类用 step_through 或 param_sim 画出图形; 让读者"动手改变某个量并
   观察(或听到)结果", 而非只读文字。
3. 每个 block 写明 block_id、type、intent(教学意图) 与 content_spec(结构化内容, 非代码)。
4. 交互块写 interaction_spec.invariants(交互后必须成立的属性, 供测试断言)。
5. 数学公式用 LaTeX: 行内 $...$、行间 $$...$$ (会渲染为 MathML)。
6. **内容必须回扣 pedagogy(关键, 直接决定教学质量)**:
   - 逐条澄清上面 misconceptions 里的**每一个**误解——在某个 block 的正文/explain/
     quiz 解析中点名该误区并纠正(如"很多同学以为……, 其实……")。
   - 在可视化(param_sim/step_through)与正文里用 central_phenomenon 的措辞明确锚定
     "改变哪个量 → 观察到什么变化", 让交互直指中心现象。
   - 至少一道 quiz 题专门针对一个高频误解来设置干扰项。

可用 block type: text, callout, figure, code, section, quiz, flashcards,
timeline, concept_graph, interactive_demo, param_sim, step_through, animation,
audio, deep_dive, user_note。

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
- audio: {{ "waveform": "sine"|"square"|"sawtooth"|"triangle",
           "controls": [{{"name","label","min","max","step","default","maps"}}], "explain": str }}
  maps ∈ frequency(Hz, 控音高)|gain(0~1, 控响度)|detune; 用于"用声音呈现"频率/振幅。
  例: 频率 controls=[{{name:"f",label:"频率(Hz)",min:110,max:880,default:440,maps:"frequency"}},
      {{name:"v",label:"音量",min:0,max:1,step:0.01,default:0.3,maps:"gain"}}]。

输出严格符合 KnowlingSpec schema 的 JSON, 顶层字段:
knowledge_point_id, pedagogy, blocks, render_target, version。"""


# Blocks that count as "rich media" — the floor we guarantee on every card.
VISUAL_TYPES = frozenset({
    "param_sim", "interactive_demo", "animation", "concept_graph", "step_through",
    "figure", "timeline", "audio",
})

_REPAIR_INSTRUCTION = (
    "上一版没有任何可视化/可交互块, 不达标。请**必须**至少加入一个 "
    "param_sim / interactive_demo / animation / concept_graph / step_through 块"
    "(函数/几何/随量变化优先 param_sim 画二维曲线; 仅当涉及声音/声波/音高/振动发声时再加 audio), "
    "让这张卡能动手交互或看到图形, 并尽量减少纯文字页。重新输出完整 KnowlingSpec JSON。"
)


def _has_visual(spec: KnowlingSpec) -> bool:
    return any(b.type in VISUAL_TYPES for b in spec.blocks)


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
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]

    def _build(data) -> KnowlingSpec:
        data.setdefault("knowledge_point_id", kp.id)
        data.setdefault("render_target", render_target)
        return KnowlingSpec.from_dict(data)

    data, comp = complete_json(provider, messages, task="plan",
                              temperature=0.5, max_tokens=8000, meta={"kp": kp.to_dict()})
    if not isinstance(data, dict):
        raise ValueError(
            "spec planner did not return valid JSON. Raw head:\n"
            + ((comp.text[:400]) if comp else "")
        )
    spec = _build(data)

    # Modality guarantee: every card must carry rich media. If the plan came back
    # text-only, re-plan once with a hard instruction and prefer the richer result.
    if not _has_visual(spec):
        data2, comp2 = complete_json(
            provider, messages + [{"role": "user", "content": _REPAIR_INSTRUCTION}],
            task="plan", temperature=0.5, max_tokens=8000, meta={"kp": kp.to_dict()})
        if isinstance(data2, dict):
            spec2 = _build(data2)
            if _has_visual(spec2):
                spec, comp = spec2, comp2

    call = ModelCall(
        stage="plan",
        provider=comp.provider,
        model=comp.model,
        prompt_tokens=comp.prompt_tokens,
        completion_tokens=comp.completion_tokens,
        cost_usd=comp.cost_usd,
    )
    return spec, call
