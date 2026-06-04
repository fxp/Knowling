# Knowling — 通用「知识点生成」模块设计文档

> **文档类型**：给 Agent 开发用的工程设计文档（Engineering Design Doc，可直接交给 Claude Code / Cursor / aider 实现）
> **版本**：v0.1 · 2026-06
> **一句话**：输入一个**细小、明确的知识点**，输出一个经过质检的、自包含的、高质量可交互学习组件（Knowling）。
> **命名**：单个产物 = `Knowling`（know + ling，知识幼体）；模块/孵化器 = `Knowling Engine`。

---

## 0. 文档定位与读者

本文档的读者是**实现该模块的 coding agent**（以及指挥它的工程师）。因此：

- 所有架构都给到**数据结构 + 接口签名 + 伪代码**级别，可直接落地。
- 设计原则部分给出**为什么这样选**，便于 agent 在歧义处做出符合意图的决策。
- 融合来源标注清楚（哪段思想/代码来自哪个开源项目 + license），便于合规复用。
- 模块边界遵循 **「Skill (开放) + Server API (护城河)」** 模式：生成蓝图/编排逻辑开源为 Skill，质检模型与块组件库可作为闭源 Server API。

---

## 1. TL;DR 与核心设计决策

| # | 决策 | 理由 | 来源 |
|---|------|------|------|
| D1 | **以「知识点 → 单个自包含组件」为原子单位**，而非「主题 → 整门课」 | 用户诉求是细小知识点的精品组件，组件可被宿主系统自由组合 | 区别于 OpenMAIC/DeepTutor 的整书/整课定位 |
| D2 | **引入中间表示 `KnowlingSpec`（蓝图），与最终渲染代码解耦** | 蓝图可被人/agent 审阅、增量编辑，避免「doc-code drift」；蓝图层是 approval gate | VIVIDOC 的 DocSpec |
| D3 | **生成后必须过「质检闭环」才算完成** | 纯代码执行无法捕捉视觉与交互质量，学习组件尤其依赖这两者 | WebGen-Agent 的多级视觉反馈 |
| D4 | **质检用三维信号：渲染分 + 交互分 + 教学分**，比通用建站多一维 | 学习组件正确性 ≠ 能跑，还要教学有效 | WebGen-Agent(2维) + 本设计扩展教学维 |
| D5 | **成本分离**：强 LLM 做规划+编码，小 VLM 做截图质检，中模型驱动 GUI 测试 | WebGen-Agent 验证小 VLM 足以做质检，可大幅降本 | WebGen-Agent |
| D6 | **块（Block）化组装**，组件 = 若干可交互块的有序集合 | 复用、可测、可单块重生成 | DeepTutor 13-block 体系 |
| D7 | **可选 RAG grounding**，知识点可锚定到用户知识库 | 防幻觉，支持企业私有知识 | DeepTutor(LlamaIndex) |
| D8 | **知识点不是孤立的**：产出携带前置/后继依赖，可拼成知识图谱 | 支持「知识点导航」与学习路径 | Concept Explorer / OpenMAIC MAIC-Craft |

---

## 2. 开源项目深度拆解

### 2.1 DeepTutor (HKUDS) — 块化编译管线 + Agent-Native 接口

**License**: Apache-2.0 · **Stack**: Python 72% + TypeScript 26%, FastAPI + Next.js 16 · `github.com/HKUDS/DeepTutor`

**可借鉴的核心**：

1. **Book Engine 的 13 种块类型**：`text, callout, quiz, flash cards, code, figure, deep dive, animation, interactive demo, timeline, concept graph, section, user note`，每种块有独立的可交互渲染组件。这是 Knowling 块注册表的直接蓝本。
2. **多 agent 编译管线**：`提纲提议 → 检索来源 → 合成章节树 → 规划每页 → 编译每个块`，配实时进度时间线。Knowling 的管线是它的「单知识点裁剪版」。
3. **Tools / Capabilities 插件模型**：工具与工作流解耦——工作流编排推理，工具按需组合。Knowling 沿用此解耦。
4. **SKILL.md 注入机制**：用户写 `SKILL.md`（name / description / triggers / Markdown body）定义教学人格，激活时注入 system prompt。Knowling 用同一机制定义「风格」与「难度档」。
5. **Agent-Native CLI**：每个能力 `deeptutor run <capability> <msg>`，双输出模式（rich 给人 / line-delimited JSON 给 agent）。Knowling 的 CLI 直接抄此设计。
6. **关键利好**：DeepTutor 原生支持 `zhipu` binding（`https://open.bigmodel.cn/api/paas/v4`）和 `anthropic` binding，模型层即插即用。

**局限**：定位是「整本 living book」，没有「单知识点精品组件」的独立产物概念；可交互块的质量靠 LLM 一次生成，无强制质检闭环。

### 2.2 WebGen-Agent (CUHK MMLab) — 视觉质检闭环（最值钱的部分）

**License**: 开源（含 workflow / 训练代码 / 权重）· `github.com/mnluzimu/WebGen-Agent`

**可借鉴的核心 —— 这是 Knowling 质检层的骨架**：

每个生成 step 由三动作组成：`code generation → code execution → feedback gathering`。反馈分两级：

- **截图反馈** `F_shot = <Description, Score_shot, Suggestions_shot>`：由一个**独立的小 VLM**（论文用 Qwen2.5-VL-32B）看落地页截图，判断视觉完整性与美观，给分 + 改进建议。
- **GUI-agent 反馈** `F_gui = <Score_gui, Suggestions_gui>`：仅当截图分达标后才启动，由 GUI agent 真实操作页面（点按钮、走流程），验证功能是否如指令所述。
- **回溯机制**：连续 5 步报错则回退到「最佳前序步」。
- **选优机制**：轨迹结束时选最佳步还原代码——**先选 `Score_gui` 最高，再在其中选 `Score_shot` 最高，仍并列取最新**。

**关键洞察**：

- **成本分离**——强 LLM 负责编码（贵），小开源 VLM 负责质检（便宜），实验证明小 VLM 足够。
- **效果**：Claude-3.5-Sonnet 的准确率从 26.4% → 51.9%，外观分 3.0 → 3.9。
- （可选进阶）**Step-GRPO**：把 `Score_shot + Score_gui` 作为 step-level reward 训练小模型，让 7B 模型逼近闭源模型。Knowling 若要训练自有质检/生成模型，可复用此 reward 设计。

**为 Knowling 的扩展**：通用建站只需「好看 + 能用」两维；学习组件要再加一维**教学分** `F_peda`（准确性 / 是否引导注意力 / 是否有 explorable 探索价值）。

### 2.3 Concept Explorer — 知识点拆解与依赖图

**License**: MIT · **Stack**: FastAPI + ECharts + networkx · `github.com/dhnanjay/concept_explorer`

**可借鉴的核心**：

- **概念裂变**：给一个根概念，LLM 返回 4–5 个相关子概念（核心组件 / 原理 / 应用），用 `networkx` 维护节点与边，转 JSON 树喂前端。
- **SSE 流式**：用 `sse-starlette` 把逐步生成的图谱推到前端（生成时即可见）。
- **ECharts 可交互树渲染**。

**用途**：Knowling 的 **Decompose 阶段**（把宽泛主题拆成原子知识点 + 依赖图）与 **导航层**（多个 Knowling 串成可点击的知识图谱）直接复用此模式。

**局限**：产物是知识树/导航，不是富交互的学习组件本身——它是 Knowling 的「上游」与「外壳」，不是「内核」。

### 2.4 OpenMAIC (清华 THU-MAIC) — 多模态内容提取与课程规划

**Stack**: LangGraph 多 agent 编排 · `github.com/THU-MAIC/OpenMAIC` · 内置 OpenClaw 集成

**可借鉴的核心**：

- **MAIC-Craft 模块**：`多模态内容提取 + 课程规划 + 自动生成 agent 角色`。其「从 PDF/topic 抽取 → 规划结构」的前处理流程，可作为 Knowling 处理**用户上传材料**时的提取器。
- **低成本基线**：约 30 分钟、< $2 生成一门完整课程——可作为 Knowling 单组件成本预算的对照锚点（单 Knowling 目标应 < $0.1）。
- **OpenClaw 集成范式**：从飞书/Slack/Telegram 直接触发生成。Knowling 可沿此把生成入口接进 IM。

**局限**：重在「沉浸式课堂 + 多 agent 陪伴」，产物是课堂场景而非可嵌入组件；LangGraph 编排偏重，单知识点场景下需裁剪。

### 2.5 VIVIDOC — DocSpec 结构化中间表示

**类型**：研究系统（arXiv 2603.01912），human-agent 协作生成可交互教育文档。

**可借鉴的核心 —— 这是 Knowling 蓝图层的思想来源**：

- **DocSpec 编辑接口**：不让 agent 直接吐 HTML，而是先生成一个**结构化的文档规格（DocSpec）**，人/agent 在 spec 层引导生成、做增量编辑，再由 spec 编译成交互文档。
- **盲评结论**：相比朴素 agentic 生成，结构化 spec 在内容丰富度、交互质量、视觉质量上显著更优。

**为 Knowling 的映射**：`KnowlingSpec` = 知识点级的 DocSpec。它是「可审阅、可 diff、可局部重生成」的蓝图，也是质量与可控性的关键来源。

### 2.6 理论根基 — Explorable Explanations (Bret Victor)

Knowling 的「高质量」标准锚定于此：可交互模拟 + 引导性叙述，**主动让读者用行为检验预期**，而非被动阅读。Bret Victor 强调它区别于「孤立的交互 widget」之处在于——**刻意引导读者注意力到特定现象**。这条直接写进质检的「教学分」评分准则。

### 2.7 融合矩阵（谁贡献什么）

| 能力层 | 主要来源 | 次要来源 |
|--------|----------|----------|
| 知识点拆解 / 依赖图 | Concept Explorer | OpenMAIC MAIC-Craft |
| 材料提取（PDF/多模态） | OpenMAIC MAIC-Craft | DeepTutor RAG |
| 中间蓝图（Spec 层 / approval gate） | VIVIDOC DocSpec | 用户 Commerce Harness 的 spec-gate |
| 块体系 / 块编译 | DeepTutor 13-block | — |
| 可交互组件渲染 | DeepTutor + frontend-design | Explorable Explanations |
| 质检闭环（渲染+交互+教学） | WebGen-Agent | 本设计扩展教学维 |
| RAG grounding | DeepTutor (LlamaIndex) | — |
| Agent 接口 (CLI/SKILL.md/JSON) | DeepTutor | 用户既有 Skill 习惯 |
| 导航 / 知识图谱外壳 | Concept Explorer (ECharts) | — |

---

## 3. Knowling 融合架构

### 3.1 设计原则

1. **Spec-first，code-second**：先有可审阅蓝图，再编译代码（D2）。
2. **质检不可绕过**：组件未过质检闭环不得标记为 `ready`（D3/D4）。
3. **块可独立重生成**：质检失败时只重编译失败的块，不整体重来。
4. **模型可插拔**：所有 LLM/VLM 调用走统一 provider 抽象，默认 GLM 系，支持 Anthropic/OpenAI/本地。
5. **产物自包含**：单个 Knowling 默认编译为**单文件**（React 单组件或 self-contained HTML），无外部运行时依赖，便于嵌入与分发。
6. **开放/护城河分层**：编排与 Spec schema 开源；质检模型、块组件精品库、训练数据闭源。

### 3.2 四层架构

```
┌──────────────────────────────────────────────────────────────┐
│  L4  接口层 Interface                                          │
│      CLI · MCP Tool · SKILL.md · Server API · IM 触发(OpenClaw)│
├──────────────────────────────────────────────────────────────┤
│  L3  编排层 Orchestration  (Knowling Engine)                   │
│      Decompose → Plan(Spec) → Retrieve → Compile → QA → Assemble│
├──────────────────────────────────────────────────────────────┤
│  L2  能力层 Capabilities (插件化, 工具与工作流解耦)            │
│      ┌──────────┬───────────┬──────────┬─────────────────┐   │
│      │ Block    │ Spec      │ QA       │ Retriever       │   │
│      │ Compiler │ Planner   │ Inspector│ (RAG, 可选)     │   │
│      └──────────┴───────────┴──────────┴─────────────────┘   │
├──────────────────────────────────────────────────────────────┤
│  L1  基座层 Foundation                                        │
│      Provider 抽象(LLM/VLM/GUI-agent) · Block 注册表 · 沙箱   │
│      (headless 浏览器渲染+截图) · 知识图谱存储                │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 数据流（单知识点）

```
KnowledgePoint
   │  ① Decompose (可选: 大主题→多知识点+依赖图)
   ▼
KnowlingSpec  ← ② Plan  ←─ (可选 ③ Retrieve grounding)
   │            [APPROVAL GATE: 人/agent 可审阅、编辑、批准]
   ▼
Block[]       ← ④ Compile (逐块编译为可交互代码)
   │
   ▼
Candidate Knowling ──► ⑤ QA Loop ──┐
   ▲                                │ 失败 → 定位失败块 → 回 ④ 重编译该块
   └──────── 选优/回溯 ◄────────────┘ 通过
   │
   ▼
Knowling (ready)  → ⑥ Assemble (挂载到知识图谱导航)
```

---

## 4. 核心数据结构

> 用 TypeScript interface 表达（agent 友好，也可直接转 JSON Schema / Pydantic）。

### 4.1 KnowledgePoint（输入）

```typescript
interface KnowledgePoint {
  id: string;                    // 稳定 ID, e.g. "calc.derivative.chain-rule"
  title: string;                 // "链式法则"
  description: string;           // 知识点的精确范围描述（越具体越好）
  learning_objectives: string[]; // 学完后能做什么（用于教学分评分基准）
  difficulty: "intro" | "core" | "advanced";
  prerequisites?: string[];      // 前置知识点 id
  followups?: string[];          // 后继知识点 id
  audience?: string;             // "高中生" | "有微积分基础的工程师" ...
  source_refs?: SourceRef[];     // 可选: grounding 来源 (RAG/上传材料)
  locale?: string;               // 默认 "zh-CN"
}
```

### 4.2 KnowlingSpec（中间蓝图 / approval gate）

> 借鉴 VIVIDOC DocSpec。这是**唯一可被人审阅与 diff 的层**，是质量与可控性的命门。

```typescript
interface KnowlingSpec {
  knowledge_point_id: string;
  pedagogy: {
    hook: string;                // 开场如何抓住注意力
    central_phenomenon: string;  // Bret Victor: 要引导读者注意的"那个现象"
    misconceptions: string[];    // 常见误解 (质检会检查是否澄清)
    aha_moment: string;          // 期望的"顿悟点"
  };
  blocks: BlockSpec[];           // 有序块编排
  render_target: "react" | "html";
  est_cost_usd?: number;         // 规划期成本预估
  version: number;
}

interface BlockSpec {
  block_id: string;
  type: BlockType;               // 见 §7 注册表
  intent: string;                // 这个块要达成的教学意图（喂给编译器）
  content_spec: object;          // 块特定的内容字段（结构化, 非代码）
  interaction_spec?: {           // 可交互块才有
    controls: Control[];         // 滑块/输入/按钮/拖拽…
    invariants: string[];        // 交互后必须保持的属性 (GUI 测试断言用)
    guided_steps?: string[];     // explorable: 引导读者做哪些探索动作
  };
  grounding?: SourceRef[];       // 该块依据的来源
}
```

### 4.3 Block 体系基类

```typescript
type BlockType =
  // —— 静态/叙述 (DeepTutor) ——
  | "text" | "callout" | "figure" | "code" | "section"
  // —— 评测/记忆 (DeepTutor) ——
  | "quiz" | "flashcards"
  // —— 结构/关系 (DeepTutor + Concept Explorer) ——
  | "timeline" | "concept_graph"
  // —— 可交互探索 (DeepTutor + Explorable Explanations) —— ★ Knowling 重心
  | "interactive_demo"    // 通用可调参数演示
  | "param_sim"           // 滑块驱动的模拟 (Bret Victor 式)
  | "step_through"        // 逐步推演 (证明/算法/流程) — 借 VIVIDOC/Explorable Theorems
  | "animation"           // 受控动画 (Manim 风/CSS/Canvas)
  // —— 元 ——
  | "deep_dive" | "user_note";
```

### 4.4 Knowling（输出产物）

```typescript
interface Knowling {
  id: string;
  knowledge_point_id: string;
  spec: KnowlingSpec;            // 可追溯的蓝图
  artifact: {
    format: "react" | "html";
    entry: string;               // 单文件路径
    self_contained: boolean;     // 默认 true
  };
  qa: QAReport;                  // 见 §6
  graph_links: { prerequisites: string[]; followups: string[] };
  status: "draft" | "qa_failed" | "ready";
  created_at: string;
  model_trace: ModelCall[];      // 成本/模型审计
}
```

---

## 5. 生成管线（6 阶段）

```python
def generate_knowling(kp: KnowledgePoint, cfg: Config) -> Knowling:
    # ① DECOMPOSE — 仅当输入是宽泛主题时触发 (来源: Concept Explorer)
    if is_broad_topic(kp):
        kps, dep_graph = decompose_to_atoms(kp, cfg.llm)   # 返回原子知识点 + 依赖
        return [generate_knowling(k, cfg) for k in kps]    # 递归到原子

    # ③ RETRIEVE (可选, grounding) — 来源: DeepTutor RAG / OpenMAIC 提取
    grounding = retriever.fetch(kp.source_refs) if kp.source_refs else None

    # ② PLAN — 生成蓝图 (来源: VIVIDOC DocSpec)
    spec = spec_planner.plan(kp, grounding, cfg.llm)        # 强 LLM
    spec = approval_gate(spec)                              # 人/agent 审阅，可编辑

    # ④ COMPILE — 逐块编译为可交互代码 (来源: DeepTutor block compiler)
    blocks = [block_compiler.compile(b, kp, grounding, cfg.llm) for b in spec.blocks]
    candidate = assemble_artifact(blocks, spec.render_target)

    # ⑤ QA LOOP — 质检闭环 (来源: WebGen-Agent, 三维扩展)
    candidate = qa_loop(candidate, spec, cfg)

    # ⑥ ASSEMBLE — 挂载知识图谱 (来源: Concept Explorer)
    knowling = finalize(candidate, spec, kp)
    graph_store.upsert(knowling)
    return knowling
```

每阶段的关键点：

- **① Decompose**：仅在输入过宽时触发；输出原子知识点 + `networkx` 依赖图。原子性判据：能用 1 个中心现象 + ≤6 个块讲清。
- **② Plan**：强 LLM 产出 `KnowlingSpec`。这里**禁止生成代码**，只产结构化蓝图。
- **②.5 Approval Gate**：默认 agent 自动批准；可配置为必须人审（企业/高风险场景）。蓝图可 diff、可版本化。
- **③ Retrieve**：可选。锚定到知识库/上传材料，每个块记录 `grounding` 以便质检核对事实。
- **④ Compile**：每块独立编译，可并行。编译器按 `BlockType` 路由到对应的块模板 + 生成 prompt。
- **⑤ QA Loop**：见 §6，不通过则只重编译失败块。
- **⑥ Assemble**：写入图谱，生成前置/后继链接，供导航层使用。

---

## 6. 质检闭环（Knowling 的护城河）

> 在 WebGen-Agent 的「渲染分 + 交互分」基础上加入**教学分**，三维质检。

### 6.1 单轮质检的三个信号

```python
def qa_step(artifact, spec) -> StepFeedback:
    # 0. 沙箱渲染：headless 浏览器加载组件，截图 + 注入交互探针
    shot = sandbox.render_and_screenshot(artifact)

    # F1. 渲染反馈 — 小 VLM (便宜) : 视觉完整性/美观/无错位
    F_render = vlm.assess_screenshot(shot)
    #   = { description, score_render(0-5), suggestions[] }

    if F_render.score_render < cfg.render_threshold:
        return StepFeedback(stage="render", **F_render)   # 先修外观

    # F2. 交互反馈 — GUI-agent (中模型) : 真实操作控件, 校验 invariants
    F_interact = gui_agent.test(artifact, spec.interaction_assertions())
    #   = { score_interact(0-5), suggestions[] }
    #   断言例: 拖动滑块后曲线更新; quiz 选错给出解释; flashcard 可翻面

    if F_interact.score_interact < cfg.interact_threshold:
        return StepFeedback(stage="interact", **F_interact)

    # F3. 教学反馈 — 强 LLM (评审) : 锚定 Explorable Explanations 准则
    F_peda = judge_llm.assess_pedagogy(artifact_text, spec.pedagogy, grounding)
    #   评分准则:
    #   - 事实准确 (对照 grounding, 无幻觉)
    #   - 是否引导注意力到 central_phenomenon (Bret Victor)
    #   - 是否澄清 spec.misconceptions
    #   - 是否真有"探索价值"(可调参数会改变可观察结果, 而非装饰)
    #   - 是否达成 learning_objectives
    #   = { score_peda(0-5), suggestions[] }

    return StepFeedback(stage="pedagogy", **F_peda)
```

### 6.2 回溯与选优（来源 WebGen-Agent）

```python
def qa_loop(candidate, spec, cfg) -> Knowling:
    memory = []                      # [(state, score_render, score_interact, score_peda)]
    state = candidate
    for step in range(cfg.max_qa_steps):
        fb = qa_step(state, spec)
        memory.append((state, fb.scores))
        if fb.all_pass():            # 三维全部达标
            break
        # 只重编译 fb 指出的失败块
        failed = locate_failed_blocks(fb, spec)
        state = recompile_blocks(state, failed, fb.suggestions, cfg.llm)
        if consecutive_render_errors(memory) >= 5:   # 回溯
            state = backtrack_to_best(memory)
    # 选优: 先 peda 最高 → 再 interact → 再 render → 仍并列取最新
    best = select_best(memory, keys=["peda", "interact", "render", "recency"])
    return best
```

### 6.3 成本分离（关键省钱设计）

| 角色 | 模型档位 | 默认建议 | 调用频率 |
|------|----------|----------|----------|
| Spec 规划 | 强 LLM | GLM-4.6 / Claude Opus | 1×/知识点 |
| 块编译 | 强 LLM (coding) | GLM-4.6 / Claude Sonnet | N×块 |
| 截图质检 | 小 VLM | GLM-4V / Qwen-VL | 多×/轮 |
| GUI 交互测试 | 中模型 | GLM-4-Air | 1×/轮(达标后) |
| 教学评审 | 强 LLM | GLM-4.6 / Claude | 1×/轮(前两维过后) |

> WebGen-Agent 已证明小 VLM 做视觉质检足够；把最贵的强 LLM 限制在规划/编码/终审，单 Knowling 成本可压到 < $0.1。

---

## 7. Block 注册表（实现清单）

每个块需实现：`schema`（content_spec 校验）、`prompt`（编译用）、`renderer`（前端组件）、`qa_assertions`（交互断言生成器）。

| BlockType | 交互性 | content_spec 关键字段 | QA 交互断言示例 | 渲染技术建议 |
|-----------|--------|----------------------|-----------------|--------------|
| `text` | 否 | `md` | — | Markdown |
| `callout` | 否 | `variant, md` | — | 样式盒 |
| `figure` | 否 | `src/svg, caption` | 图像加载成功 | SVG/img |
| `code` | 弱 | `lang, code, runnable?` | 运行按钮产出预期 | Shiki + 可选沙箱 |
| `quiz` | 是 | `question, options, answer, explain` | 选错显示解释；选对标记正确 | React state |
| `flashcards` | 是 | `cards[{front,back}]` | 可翻面；可下一张 | 翻转动画 |
| `timeline` | 是 | `events[{t,label,detail}]` | 点击节点展开详情 | 横向滚动 |
| `concept_graph` | 是 | `nodes, edges` | 点击节点高亮邻居 | ECharts (Concept Explorer) |
| `interactive_demo` | 是 | `model, controls, outputs` | 改输入→输出更新 | React |
| `param_sim` | 是 | `params[], compute_fn, viz` | 拖滑块→可视化连续变化 | Canvas/SVG + slider |
| `step_through` | 是 | `steps[{state,explain}]` | 上/下一步切换状态 | 状态机 |
| `animation` | 半 | `keyframes, autoplay?` | 可暂停/重播 | CSS/Canvas/Lottie |
| `deep_dive` | 是 | `summary, expanded_md` | 可展开/收起 | Disclosure |
| `user_note` | 是 | `placeholder` | 可输入并本地保存 | textarea (内存态) |

> **重心是 `param_sim` / `step_through` / `interactive_demo`** —— 这三类才是「细小知识点」真正出彩的地方（一个滑块讲清一个公式的行为），也是 explorable explanation 的精髓所在。

---

## 8. 模块接口

### 8.1 CLI（仿 DeepTutor，双输出）

```bash
# 单知识点生成
knowling gen "链式法则" \
  --objectives "能对复合函数求导,能解释为何相乘" \
  --difficulty core --audience "高中生" \
  --format react --output ./out/

# 宽主题 → 自动拆解为多个 Knowling
knowling gen-topic "傅里叶变换" --decompose --max-points 8

# 仅出蓝图(给人审)
knowling plan "梯度下降" -f json     # 输出 KnowlingSpec, 不编译

# 从蓝图编译(审批后)
knowling compile spec.json --format html

# 双输出: rich 给人 / json 给 agent
knowling gen "..." -f rich    # 终端彩色
knowling gen "..." -f json    # line-delimited JSON 事件流(进度/成本/QA分)
```

### 8.2 MCP Tool（给其它 agent 调用）

```json
{
  "name": "knowling_generate",
  "description": "Generate a self-contained interactive learning component for ONE knowledge point",
  "input_schema": {
    "knowledge_point": "KnowledgePoint",
    "format": "react | html",
    "rag_kb": "string | null",
    "approval": "auto | human"
  },
  "output": { "knowling": "Knowling", "stream": "QA progress events" }
}
```

### 8.3 SKILL.md（给 Claude Code / Cursor / aider）

提供 `SKILL.md`，body 内描述：何时触发（用户说「给这个知识点做个可交互组件」）、如何调 CLI、Spec schema 摘要、风格档选择。复用用户既有的「SKILL.md 兼容多 agent」习惯。可同时提供多个风格 skill（`knowling-minimal` / `knowling-rich-explorable` / `knowling-exam-prep`），通过 triggers 区分。

### 8.4 Server API（护城河）

```
POST /v1/knowling/plan      → KnowlingSpec        (开放, 逻辑可开源)
POST /v1/knowling/compile   → Knowling(draft)
POST /v1/knowling/qa        → QAReport            (闭源: 质检模型/断言库)
GET  /v1/knowling/{id}                            
GET  /v1/graph/{kp_id}      → 知识图谱邻域 (导航)
```

> **开放/护城河切分**：Spec schema + 编排 + CLI 开源为 Skill；质检模型、精品块组件库、教学评分准则与训练数据走 Server API。

---

## 9. 工程骨架（建议目录结构）

```
knowling/
├── SKILL.md                       # agent 入口
├── pyproject.toml
├── knowling/
│   ├── engine.py                  # L3 编排: generate_knowling()
│   ├── capabilities/
│   │   ├── decompose.py           # ← Concept Explorer
│   │   ├── retriever.py           # ← DeepTutor RAG (LlamaIndex)
│   │   ├── spec_planner.py        # ← VIVIDOC DocSpec
│   │   ├── block_compiler.py      # ← DeepTutor block engine
│   │   └── qa/
│   │       ├── loop.py            # ← WebGen-Agent backtrack/select-best
│   │       ├── render_vlm.py      # 截图质检 (小 VLM)
│   │       ├── gui_agent.py       # 交互测试
│   │       └── pedagogy_judge.py  # 教学评审 (本设计扩展)
│   ├── blocks/                    # 块注册表 (schema+prompt+assertions)
│   │   ├── registry.py
│   │   ├── param_sim.py
│   │   ├── step_through.py
│   │   └── ...
│   ├── providers/                 # LLM/VLM/GUI 统一抽象 (默认 zhipu)
│   ├── sandbox/                   # headless 渲染 + 截图 + 交互探针
│   ├── schema/                    # KnowledgePoint / KnowlingSpec / Knowling
│   └── cli.py                     # ← DeepTutor CLI 双输出范式
├── web/
│   ├── renderers/                 # 13 类块的 React/HTML 组件
│   └── navigator/                 # ECharts 知识图谱外壳 (← Concept Explorer)
└── tests/
    ├── golden_specs/              # 蓝图回归
    └── qa_fixtures/               # 质检断言夹具
```

---

## 10. 关键 Prompt 模板（骨架）

### 10.1 Spec 规划（产蓝图，禁止出代码）

```
你是学习组件的教学设计师。针对单个知识点产出 KnowlingSpec（JSON），不要写任何代码。
知识点: {kp.title} — {kp.description}
学习目标: {kp.objectives}
受众/难度: {kp.audience} / {kp.difficulty}
[若有] 依据材料: {grounding}

要求:
1. 先定 pedagogy: 抓手 hook、要引导注意的"中心现象"central_phenomenon、
   常见误解 misconceptions、期望顿悟点 aha_moment。
2. 选 ≤6 个 block 并排序。优先 param_sim/step_through/interactive_demo——
   让读者能"动手改变某个量并观察结果"，而非只读文字。
3. 每个 block 写明 intent(教学意图) 与 content_spec(结构化内容, 非代码)。
4. 交互块写 interaction_spec.invariants(交互后必须成立的属性, 供测试断言)。
输出严格符合 KnowlingSpec schema 的 JSON。
```

### 10.2 块编译

```
把以下 BlockSpec 编译成一个自包含的 {react|html} 块组件。
BlockSpec: {block_spec}
约束:
- 无外部运行时依赖; 所有状态用组件内 state(禁止 localStorage)。
- 实现 interaction_spec.controls; 保证 invariants 成立。
- explorable 准则: 可调量必须真实驱动可观察输出的变化。
- 风格遵循 frontend-design skill 的设计令牌。
只输出代码。
```

### 10.3 教学评审（终审）

```
作为教学质量评审，对该学习组件打分(0-5)并给出可执行建议。
锚定 Explorable Explanations 准则:
- 事实是否准确(对照依据材料, 标出任何幻觉)
- 是否把读者注意力引导到 central_phenomenon: {spec.pedagogy.central_phenomenon}
- 是否澄清了这些误解: {spec.pedagogy.misconceptions}
- 可交互元素是否有真实探索价值(改变输入会改变可观察结果)
- 是否达成学习目标: {kp.objectives}
输出 { score_peda, suggestions[] }。
```

---

## 11. 模型选型建议

- **默认全栈 GLM**（智谱内部场景）：规划/编码 `GLM-4.6`，截图质检 `GLM-4V`，GUI 测试 `GLM-4-Air`，终审 `GLM-4.6`。Provider 抽象层默认 `zhipu` binding（DeepTutor 已验证可用）。
- **混合**：编码/终审用 Claude Sonnet（代码与评审质量），质检用 GLM-4V（省钱），符合成本分离。
- **完全本地**：vLLM 部署 Qwen2.5-Coder + Qwen2.5-VL，对标 WebGen-Agent 原配置。
- **进阶**：若量大，按 WebGen-Agent 的 Step-GRPO 训练自有小模型做块编译，reward = 渲染分 + 交互分 +（可加）教学分。

---

## 12. 实施路线图

| 阶段 | 目标 | 交付 | 复用 |
|------|------|------|------|
| **P0 骨架** (1-2 周) | 跑通「知识点→蓝图→单块→渲染」最小闭环 | CLI `plan`+`compile`，3 个块(text/quiz/param_sim)，无质检 | DeepTutor CLI/block 范式 |
| **P1 质检** (2-3 周) | 接入三维质检 + 回溯选优 | sandbox 截图、render_vlm、gui_agent、pedagogy_judge | WebGen-Agent 闭环 |
| **P2 全块** (2-3 周) | 13 类块全实现 + RAG grounding | 块注册表完整、retriever | DeepTutor blocks + LlamaIndex |
| **P3 拆解+导航** (2 周) | 大主题自动拆解 + 知识图谱外壳 | decompose、ECharts navigator | Concept Explorer |
| **P4 接口化** (1-2 周) | MCP Tool + SKILL.md + Server API + IM 触发 | 完整接口层 | DeepTutor SKILL.md / OpenMAIC OpenClaw |
| **P5 (可选) 自训** | Step-GRPO 训练块编译小模型 | 降本 | WebGen-Agent 训练代码 |

---

## 13. 可复用开源代码清单（合规）

| 项目 | License | 直接复用什么 | 注意 |
|------|---------|--------------|------|
| DeepTutor | Apache-2.0 | block engine 思路、CLI 双输出、provider 抽象、SKILL.md 注入；可参考 `deeptutor/` 源码 | 商用友好；保留版权声明 |
| WebGen-Agent | 开源(查仓库 LICENSE) | 质检闭环 workflow、backtrack/select-best、Step-GRPO 训练代码 | 用前确认具体 license |
| Concept Explorer | MIT | 概念裂变 + networkx + SSE + ECharts 树渲染 | 商用友好 |
| OpenMAIC | 查仓库 LICENSE | MAIC-Craft 提取/规划思路、OpenClaw 触发范式 | LangGraph 偏重，按需裁剪 |
| VIVIDOC | 研究系统 | DocSpec 中间表示的设计思想（非代码移植） | 以论文方法为准 |

---

## 附录 · 参考链接

- DeepTutor: `github.com/HKUDS/DeepTutor` · arXiv 2604.26962
- WebGen-Agent: `github.com/mnluzimu/WebGen-Agent` · arXiv 2509.22644
- Concept Explorer: `github.com/dhnanjay/concept_explorer`
- OpenMAIC: `github.com/THU-MAIC/OpenMAIC`
- VIVIDOC: arXiv 2603.01912
- Explorable Explanations (Bret Victor): worrydream.com/ExplorableExplanations

---

*本文档可作为 `SKILL.md` 的设计参考或直接拆分为模块级 spec。建议先实现 P0 最小闭环验证「蓝图→param_sim 块→渲染」链路，再叠加质检。*
