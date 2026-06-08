# 接缝契约草案：Knowling(L3) ↔ 第二阶段编排层(L1/L2)

> 配套 [`phase2-adaptive-learning-mapping.md`](phase2-adaptive-learning-mapping.md)。
> 本文只定义**两层对接的契约**，不改实现；定稿后再落代码。
> 三个契约 + 一个事件机制：
> ① `KnowledgePoint` 大纲坐标　② `MasteryResult` 掌握度信号
> ③ P4 接口签名（MCP / REST）　④ 自包含卡 → 宿主的 **Quiz 结果事件**
>
> 设计原则不破：单 KP、自包含单文件、可质检。坐标/信号只是**让单元可被寻址、可回传结果**。

---

## ① KnowledgePoint 大纲坐标 + 稳定 id

现状：`KnowledgePoint` 已有稳定 `id`、`prerequisites`、`followups`（天然对应图谱节点与边）。
**只需新增一个可选 `curriculum` 字段**，向后兼容（不传则行为不变）。

```python
@dataclass
class Curriculum:
    """L0 大纲坐标。让 L1 图谱节点 ↔ Knowling 单元 1:1 寻址。"""
    syllabus_id: str            # 大纲版本, e.g. "cn-pep-math-junior"(人教版初中数学)
    grade: str                  # "初二" / "8"
    chapter: str                # "第3章 一次函数"
    section: Optional[str] = None   # "3.2 一次函数的图象"
    node_code: Optional[str] = None # 稳定路径码 "8.3.2"  ← 人读坐标
    order: Optional[int] = None     # 节内顺序

# KnowledgePoint 增一字段（其余不变）
#   curriculum: Optional[Curriculum] = None
```

**约定**
- **图谱节点 id ≡ `KnowledgePoint.id`**（机器主键，全局稳定）；`node_code` 是给人看的大纲坐标。
- 图谱的边由 L1 owns；Knowling 的 `prerequisites/followups` 仅作单元自描述，**不承担导航**。
- `curriculum` 是纯元数据，进 spec / 产物 metadata，便于 L1 回填点亮，不影响渲染。

JSON 示例：
```json
{
  "id": "kp_linear_fn_slope",
  "title": "一次函数的斜率含义",
  "difficulty": "core",
  "audience": "初中生",
  "curriculum": {"syllabus_id":"cn-pep-math-junior","grade":"初二",
                 "chapter":"第3章 一次函数","section":"3.2 图象","node_code":"8.3.2"}
}
```

---

## ② MasteryResult 掌握度信号（L3 出口 → L1 点亮）

Knowling 学习单元结束时回传的**唯一结构化结果**。主信号是 Quiz 得分；四轴（取自 get-it）为可选细化。

```python
@dataclass
class AxisScore:           # 取自 get-it 四轴；0..1
    memory: float = 0.0
    comprehension: float = 0.0
    structure: float = 0.0
    application: float = 0.0

@dataclass
class QuizOutcome:
    total: int
    correct: int
    score: float                       # correct / total
    per_question: List[Dict[str, Any]] # [{q_id,type,correct:bool,chosen,expected}]
    wrong_tags: List[str] = field(default_factory=list)  # 错因/子技能标签

@dataclass
class MasteryResult:
    kp_id: str
    knowling_id: str
    passed: bool                       # score >= pass_threshold(默认0.8)
    score: float                       # 主信号
    level: str                         # "red" | "yellow" | "green"  ← 红绿灯+强度
    quiz: QuizOutcome
    attempts: int = 1                  # 本单元重教轮数
    axes: Optional[AxisScore] = None   # 可选四轴
    reasons: List[str] = field(default_factory=list)  # 未掌握原因(供L1展示+重教)
    observed_at: str = ""
```

**约定**
- `level` 即图谱红绿灯（带强度）：`green≥0.8 / yellow 0.5–0.8 / red<0.5`（阈值可配）。
- **单调不降（get-it 的"只进不退"）由 L1 状态层强制**，不在 Knowling：Knowling 只报"本次观测"，
  L1 做 `max(历史, 本次)` 落库。文档明确职责，避免两边都做。
- `axes` 可空：MVP 只用 `score/level` 足够点亮；四轴留给后续精细化。

---

## ③ 答错重教（融入 Knowling ①）契约

信号驱动版 `refine`：是现有 `refine_knowling(spec, kp, instruction, …)` 的**薄适配器**——
把 Quiz 失败信号翻成一句改写指令，复用既有 refine + `qa/loop`。

```python
def reteach_on_result(
    spec: KnowlingSpec,
    kp: KnowledgePoint,
    outcome: QuizOutcome,        # 或 MasteryResult
    cfg: Optional[Config] = None,
    out_path: Optional[str] = None,
    emit: EventSink = _noop_sink,
) -> tuple[Knowling, str]:
    """Quiz 多数答错 → 为同一 KP 重生成更易懂的卡（降难度/换讲法/补铺垫）。
    单次重生成；'循环到答对' 由调用方(L2 会话 runner)循环驱动。"""
    instruction = _instruction_from_outcome(outcome)  # 拼: 错题/错因 + "降难度,换更直观讲法"
    return refine_knowling(spec, kp, instruction, cfg, out_path, emit)
```

**约定**
- Knowling 只负责"**给信号→出更易懂的一版**"（单 KP、自洽）；
- "**循环直到达标**"是 L2 编排：`while not result.passed and attempts<N: reteach → 再测`。
- 每轮可微调 difficulty（core→intro）与 audience，复用 spec 的既有字段。

---

## ④ 自包含卡 → 宿主的 Quiz 结果事件（关键机制）

矛盾点：卡是**自包含 HTML**，Quiz 判定在卡内 JS 完成；但 L1/L2 在卡外需要拿到结果。
解法：卡在 Quiz 完成时**对外派发一个标准事件**，宿主(iframe/webview)捕获即可——**不破坏自包含**。

卡内（quiz 块收尾时）派发：
```js
// 既兼容 iframe(postMessage) 也兼容同页(CustomEvent)
var payload = { type: "knowling:quiz-result", kp_id: "...", knowling_id: "...",
                total: 5, correct: 4, score: 0.8,
                per_question: [{q_id,type,correct,chosen,expected}], wrong_tags: [] };
window.parent && window.parent.postMessage(payload, "*");
window.dispatchEvent(new CustomEvent("knowling:quiz-result", { detail: payload }));
```

宿主(L2 runner)捕获 → 构造 `QuizOutcome/MasteryResult` → `passed?` 点亮 : `reteach`。

**约定**
- 事件名 `knowling:quiz-result` 固定为契约；`payload` 字段同 `QuizOutcome`。
- 这是 goal「学完检验 / 完成判定 / 触发重教」的真实落点，且零外部依赖。
- 现有 quiz 块已算分，只需在收尾追加这段派发（小改，自包含）。

---

## ⑤ P4 接口签名（编排层调用入口）

### MCP Tools
| tool | 入参（要点） | 出参 |
|---|---|---|
| `knowling_generate` | `kp{id,title,description,objectives,difficulty,audience,curriculum}`, `ground?[]`, `no_qa?` | `{knowling_id, status, artifact_html|path, spec}` |
| `knowling_reteach` | `knowling_id\|spec`, `quiz_outcome`, `reason?` | `{knowling_id, status, artifact_html|path}` |
| `knowling_plan` | 同 generate 的 kp | `{spec}`（仅蓝图，供审阅/缓存） |
| `knowling_quiz_eval` | `spec\|knowling_id`, `answers[]` | `MasteryResult`（宿主无法跑卡内 JS 时的服务端兜底） |

### REST（`POST /v1/knowling/*`，对齐 ROADMAP P4）
```
POST /v1/knowling/plan      {kp}                      → {spec}
POST /v1/knowling/compile   {spec, kp}                → {knowling}
POST /v1/knowling/generate  {kp, ground?, no_qa?}     → {knowling}      # plan+compile+qa
POST /v1/knowling/reteach   {spec|knowling_id, quiz_outcome} → {knowling}
POST /v1/knowling/quiz-eval {spec|knowling_id, answers} → {mastery_result}
```

**约定**
- 入参 `kp` 即 `KnowledgePoint.to_dict()`（含可选 `curriculum`）；产物含 `knowling.to_dict()`。
- 开放/护城河切分（ROADMAP P4）：`plan/compile/reteach` 逻辑开源；`qa` 质检模型 + 精品块库可闭源。

---

## 推进顺序（最小改动优先，全部向后兼容、不出范围）

1. ✅ **schema**：加 `Curriculum` + `KnowledgePoint.curriculum`（可选）。
2. ✅ **新结构**：`MasteryResult/QuizOutcome/AxisScore`（`schema/mastery.py`）。
3. ✅ **quiz 块**：收尾派发 `knowling:quiz-result` 事件（④）；`assembler` 注入 `window.__KNOWLING__.kp_id`。
4. ✅ **reteach**：`reteach_knowling` + `quiz_reteach_instruction` 薄适配器（③，复用 refine）。
5. ⬜ **P4**：MCP Tool 先行（`knowling_generate/reteach/quiz_eval`），REST 次之。

> **Phase 0（接缝地基）= 步骤 1–4，已完成**：101 项测试通过 + 真实 Chromium 端到端验证
> （答题→`knowling:quiz-result` 事件携带 `kp_id`/逐题明细派发，零 console 错误）。
> 步骤 5（P4 接口化）是更大的工程，留待 phase0 之后。
>
> ①②③④ 都落在单 KP 内，是 Knowling 自身的增强；图谱/计划/诊断仍全在第二阶段编排层。
