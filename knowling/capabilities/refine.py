"""Refine — chat-driven revision of a knowledge card (outside the card itself).

Takes the *current* KnowlingSpec plus a user instruction ("太难了", "讲深点",
"和导数是什么关系？") and produces a revised KnowlingSpec, which the engine then
compiles into a NEW card. The card stays a fixed, self-contained state; refine is
the layer that turns one fixed state into the next.

Real GLM: revises the spec intelligently. Mock: deterministic keyword heuristics
so the studio loop works offline.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional, Tuple

from ..providers.base import LLMProvider
from ..schema import BlockSpec, KnowlingSpec, ModelCall, Pedagogy
from ._extract import extract_json

SYSTEM = "你是学习组件的教学设计师。根据用户反馈修订单个知识点学习卡的 KnowlingSpec，只产结构化蓝图，不写代码。"

PROMPT = """这是当前知识点学习卡的蓝图(KnowlingSpec JSON):
{spec}

知识点: {title} — {description}
受众/难度: {audience} / {difficulty}
用户的调整诉求: "{instruction}"

请据此产出**修订后的** KnowlingSpec。可以:
- 调整难度、讲解深度、措辞、节奏;
- 增删/重排 block(仍 ≤6, 优先 param_sim/step_through/interactive_demo 这类可交互块);
- 若用户问"和某知识点的关系", 增加一个 text 或 callout block 说明这种关系;
- 若"太难/太简单", 相应降低/提高难度并简化或加深内容。

⚠️ 最重要的约束 — 不要跑题:
- 这张卡**始终在讲解「{title}」这一个知识点本身**, 不能变成讲别的知识点。
- 用户问"和X的关系"时, 只用一小块说明关系, 主体仍然讲「{title}」, 不要把卡片改写成讲 X。
- 保持 knowledge_point_id 不变, 学习目标不被稀释。

content_spec 字段约定:
- text {{"md"}}; callout {{"variant","md"}}; quiz {{"question","options","answer","explain"}};
- param_sim {{"params":[{{name,label,min,max,step,default}}],"outputs":[{{name,label,expr}}],"x_range","explain"}}
  (画 y=f(x) 曲线时用自变量 x 作横轴, 滑块只放参数);
- interactive_demo {{"controls":[{{name,label,kind}}],"outputs":[{{name,label,expr}}]}} (expr 只用 control 名);
- step_through {{"steps":[{{state,explain}}]}}。

只输出一个 JSON 对象, 两个字段:
{{"summary": "一句话说明你做了什么调整", "spec": <修订后的 KnowlingSpec>}}"""


def _kp_field(kp, name, default=""):
    return getattr(kp, name, default) or default


def refine(
    spec: KnowlingSpec,
    kp,
    instruction: str,
    provider: LLMProvider,
) -> Tuple[KnowlingSpec, ModelCall, str]:
    """Return (revised_spec, model_call, summary)."""
    if provider.name == "mock":
        new_spec, summary = _mock_refine(spec, instruction)
        call = ModelCall(stage="refine", provider="mock", model="mock-1", cost_usd=0.0)
        return new_spec, call, summary

    user = PROMPT.format(
        spec=json.dumps(spec.to_dict(), ensure_ascii=False, indent=2),
        title=_kp_field(kp, "title", spec.knowledge_point_id),
        description=_kp_field(kp, "description"),
        audience=_kp_field(kp, "audience", "通用"),
        difficulty=_kp_field(kp, "difficulty", "core"),
        instruction=instruction,
    )
    comp = provider.complete(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        task="refine", temperature=0.5, max_tokens=8000, thinking="disabled",
    )
    data = extract_json(comp.text)
    if not isinstance(data, dict):
        raise ValueError("refine did not return JSON. Head:\n" + (comp.text or "")[:400])
    spec_dict = data.get("spec", data)  # tolerate a bare spec
    summary = str(data.get("summary", "已根据你的反馈调整。"))
    spec_dict.setdefault("knowledge_point_id", spec.knowledge_point_id)
    spec_dict.setdefault("render_target", spec.render_target)
    new_spec = KnowlingSpec.from_dict(spec_dict)
    call = ModelCall(stage="refine", provider=comp.provider, model=comp.model,
                     prompt_tokens=comp.prompt_tokens, completion_tokens=comp.completion_tokens,
                     cost_usd=comp.cost_usd)
    return new_spec, call, summary


# ─────────────────────────── offline heuristic ───────────────────────────

def _mock_refine(spec: KnowlingSpec, instruction: str) -> Tuple[KnowlingSpec, str]:
    """Deterministic tweak so the studio works without an API key."""
    d = spec.to_dict()
    ins = instruction or ""
    ped = d.setdefault("pedagogy", {})
    blocks: List[dict] = d.setdefault("blocks", [])

    def add_block(b: dict, front: bool = False):
        if front:
            blocks.insert(1 if blocks and blocks[0].get("type") == "text" else 0, b)
        else:
            blocks.append(b)

    if any(k in ins for k in ("太难", "难了", "简单点", "通俗", "看不懂")):
        summary = "已降低难度：增加一个直白的类比说明，简化措辞。"
        add_block({"block_id": "refine_easy", "type": "callout",
                   "intent": "用类比降低门槛",
                   "content_spec": {"variant": "tip",
                                    "md": "**换个说法**：先别管公式，把它想成一个你能拨动的旋钮——动一下，看看结果怎么变。"}}, front=True)
    elif any(k in ins for k in ("深", "进阶", "为什么", "推导", "本质")):
        summary = "已加深：补充一个『深入一层』的展开块。"
        add_block({"block_id": "refine_deep", "type": "deep_dive",
                   "intent": "提供进阶展开",
                   "content_spec": {"summary": "深入一层：背后的原理",
                                    "expanded_md": "这里展开更严格的推导与边界条件，供学有余力者探索。"}})
    elif any(k in ins for k in ("例", "举例", "应用", "场景")):
        summary = "已增加一个具体例子块。"
        add_block({"block_id": "refine_example", "type": "text",
                   "intent": "给出具体例子",
                   "content_spec": {"md": "### 一个例子\n用一个贴近生活的具体情境，把这个知识点套进去走一遍。"}})
    elif "关系" in ins or "区别" in ins or "联系" in ins:
        summary = "已补充与相关知识点关系的说明块。"
        add_block({"block_id": "refine_relation", "type": "callout",
                   "intent": "说明与相邻知识点的关系",
                   "content_spec": {"variant": "info",
                                    "md": f"**和相关知识点的关系**：{ins.strip()}——它们是前后承接/互为特例的关系，掌握本点有助于理解那一点。"}})
    else:
        summary = f"已按『{ins.strip()}』微调讲解侧重。"
        ped["hook"] = (ped.get("hook", "") + f"（已按你的需求「{ins.strip()}」调整侧重）").strip()

    d["version"] = int(d.get("version", 1)) + 1
    return KnowlingSpec.from_dict(d), summary
