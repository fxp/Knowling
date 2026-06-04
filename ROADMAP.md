# Knowling 开发计划 (Roadmap)

> 总体设计见 [`knowling-design.md`](knowling-design.md)。本文件追踪**实现进度**与**后续计划**，随开发推进更新。

## 状态总览

| 阶段 | 目标 | 状态 |
|------|------|------|
| **P0 骨架** | 跑通「知识点→蓝图→单块→渲染」最小闭环 | ✅ 完成 |
| **P1 质检** | 三维质检闭环 + 回溯选优 | ⬜ 未开始 |
| **P2 全块** | 13 类块全实现 + RAG grounding | ⬜ 未开始 |
| **P3 拆解+导航** | 大主题自动拆解 + 知识图谱外壳 | ⬜ 未开始 |
| **P4 接口化** | MCP Tool + SKILL.md + Server API + IM 触发 | 🟡 部分（SKILL.md / CLI 已就绪）|
| **P5 自训(可选)** | Step-GRPO 训练块编译小模型 | ⬜ 未开始 |

---

## P0 · 骨架（已完成）

**交付**：最小闭环 `知识点 → KnowlingSpec → 块编译 → 自包含 HTML`。

- [x] 数据结构（`schema/`）：`KnowledgePoint` / `KnowlingSpec` / `BlockSpec` / `Knowling`，全部 JSON round-trip
- [x] Provider 抽象（`providers/`）：默认 GLM/zhipu，无 key 自动回退离线 Mock
- [x] Spec 规划（`capabilities/spec_planner.py`）：只产结构化蓝图，禁代码
- [x] 块编译（`capabilities/block_compiler.py`）：LLM 直出 HTML，不可用时回退模板
- [x] 3 个块（`blocks/`）：`text` / `quiz` / `param_sim`（滑块 + canvas 实时联动），未实现类型回退 `generic`
- [x] 编排（`engine.py`）：Plan → Approval(auto) → Compile → Assemble，逐阶段事件
- [x] 自包含 HTML 组装（`assembler.py`），内联 `.kl-*` 设计令牌
- [x] CLI 双输出（`cli.py`）：`plan` / `compile` / `gen` / `blocks`，`-f rich|json`
- [x] 测试 9 项（`tests/`）+ golden spec 夹具

**已知限制**：`status` 恒为 `draft`（无质检不得标 `ready`）；仅 html target；无 RAG / 拆解 / 质检。

---

## P1 · 质检闭环（下一步，护城河）

> 来源：WebGen-Agent 三动作 `code gen → execution → feedback`，本设计扩展教学维。

- [ ] **沙箱**（`sandbox/`）：headless 浏览器渲染组件 + 截图 + 注入交互探针
  - 选型：Playwright（Python）；产物为单文件 HTML，`file://` 直接加载
- [ ] **F1 渲染质检**（`capabilities/qa/render_vlm.py`）：小 VLM 看截图 → `{description, score_render(0-5), suggestions[]}`
- [ ] **F2 交互质检**（`capabilities/qa/gui_agent.py`）：达标后启动，真实操作控件，校验 `interaction_spec.invariants`
- [ ] **F3 教学质检**（`capabilities/qa/pedagogy_judge.py`）：强 LLM 锚定 Explorable Explanations 准则（§10.3）
- [ ] **QA loop**（`capabilities/qa/loop.py`）：回溯（连续 5 步报错回退最佳前序）+ 选优（peda→interact→render→recency）
- [ ] 失败块定位 + 只重编译失败块（不整体重来）
- [ ] 三维全过才标 `status="ready"`，写入 `QAReport`
- [ ] 块级 `qa_assertions` 生成器（每块产出可执行断言）

**验收**：对 3 个知识点生成的 Knowling 走完质检；准确率/外观分较 P0 有可量化提升。

---

## P2 · 全块 + RAG

- [ ] 补齐 13 类块：`callout` `figure` `code` `section` `flashcards` `timeline` `concept_graph` `interactive_demo` `step_through` `animation` `deep_dive` `user_note`
  - 重心：`step_through`（逐步推演）、`interactive_demo`（通用可调演示）
  - 每块实现 `schema` + `prompt` + `renderer` + `qa_assertions`（§7）
- [ ] **Retriever**（`capabilities/retriever.py`）：RAG grounding（LlamaIndex），每块记录 `grounding` 供质检核对事实
- [ ] React 单组件 target（`render_target="react"`）+ 对应渲染器
- [ ] 块级单元 + 渲染回归测试扩展

---

## P3 · 拆解 + 导航

> 来源：Concept Explorer。

- [ ] **Decompose**（`capabilities/decompose.py`）：宽主题 → 原子知识点 + `networkx` 依赖图（原子性判据：1 中心现象 + ≤6 块）
- [ ] CLI `gen-topic "<主题>" --decompose --max-points N`
- [ ] 知识图谱存储 + `graph_links` 前置/后继落库
- [ ] **Navigator**（`web/navigator/`）：ECharts 可点击知识图谱外壳
- [ ] SSE 流式拆解进度

---

## P4 · 接口化（部分完成）

- [x] SKILL.md（agent 入口）
- [x] CLI 双输出（rich / line-delimited JSON）
- [ ] **MCP Tool** `knowling_generate`（§8.2），供其它 agent 调用
- [ ] **Server API**（§8.4）：`POST /v1/knowling/{plan,compile,qa}`、`GET /v1/graph/{kp_id}`
  - 开放/护城河切分：plan/compile 逻辑开源；qa 质检模型 + 精品块库闭源
- [ ] 多风格 skill：`knowling-minimal` / `knowling-rich-explorable` / `knowling-exam-prep`
- [ ] IM 触发（OpenClaw 范式：飞书 / Slack / Telegram）

---

## P5 · 自训（可选）

- [ ] 收集质检轨迹（`score_render + score_interact + score_peda`）作 step-level reward
- [ ] Step-GRPO 训练块编译小模型（对标 WebGen-Agent，7B 逼近闭源）
- [ ] 评测：训练后模型替换块编译档位，成本/质量对比

---

## 工程约定

- **零运行时依赖**：P0 保持 stdlib-only；新增依赖（Playwright / LlamaIndex 等）按阶段加入 `pyproject.toml` optional-extras，不污染核心。
- **Provider 可插拔**：所有 LLM/VLM/GUI 调用走 `providers/` 抽象，新角色在 `factory.DEFAULT_MODELS` 注册档位。
- **质检不可绕过**：组件未过质检闭环不得标 `ready`。
- **块可独立重生成**：质检失败只重编译失败块。
- **Spec 是命门**：`KnowlingSpec` 是唯一可审阅 / diff 的层，新增块类型先扩 spec 约定再写渲染器。
