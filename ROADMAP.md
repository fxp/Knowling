# Knowling 开发计划 (Roadmap)

> 总体设计见 [`knowling-design.md`](knowling-design.md)。本文件追踪**实现进度**与**后续计划**，随开发推进更新。

## 状态总览

| 阶段 | 目标 | 状态 |
|------|------|------|
| **P0 骨架** | 跑通「知识点→蓝图→单块→渲染」最小闭环 | ✅ 完成 |
| **P1 质检** | 三维质检闭环 + 回溯选优 | ✅ 完成 |
| **P2 全块** | 13 类块全实现 + RAG grounding | ✅ 完成（React target 顺延）|
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

## P1 · 质检闭环（已完成，护城河）

> 来源：WebGen-Agent 三动作 `code gen → execution → feedback`，本设计扩展教学维。

- [x] **沙箱**（`sandbox/`）：Playwright headless Chromium 渲染 + 截图 + console 捕获；无 Playwright 时自动回退 `StaticSandbox`（结构校验，QA 仍可离线跑）
- [x] **F1 渲染质检**（`capabilities/qa/render_vlm.py`）：GLM-4V 看截图 → `{description, score(0-5), suggestions[]}`；离线走结构启发式
- [x] **F2 交互质检**（`capabilities/qa/gui_agent.py`）：达标后校验每块 `qa_assertions`（即 `interaction_spec.invariants`）
- [x] **F3 教学质检**（`capabilities/qa/pedagogy_judge.py`）：强 LLM 锚定 Explorable Explanations 准则（§10.3）；离线走覆盖度启发式
- [x] **QA loop**（`capabilities/qa/loop.py`）：回溯（连续 5 步渲染报错回退最佳前序）+ 选优（peda→interact→render→recency）
- [x] 失败块定位 + 只重编译失败块（带质检建议注入 prompt）
- [x] 三维全过才标 `status="ready"`，否则 `qa_failed`，写入 `QAReport`
- [x] 块级 `qa_assertions` 生成器（quiz/param_sim 各产出可执行断言）
- [x] CLI `--no-qa` 开关；QA 事件进入 rich/json 双输出流

**待补强（P2 一并做）**：模型驱动的 GUI agent（真实点击控件的语义 `gui_hint` 校验，当前为结构断言）；GLM-4V 视觉路径的端到端联调（需带 key + 浏览器环境）。

---

## P2 · 全块 + RAG（已完成；React target 顺延）

- [x] 补齐 13 类块：`callout` `figure` `code` `section` `flashcards` `timeline` `concept_graph` `interactive_demo` `step_through` `animation` `deep_dive` `user_note`
  - 重心已实现：`step_through`（逐步推演）、`interactive_demo`（通用 slider/number/select/checkbox/text → 表达式输出）
  - 每块实现 `validate` + `compile_prompt` + `template`(自包含渲染) + `qa_assertions`（§7）
  - `concept_graph` 用内联 canvas 实现（非 ECharts CDN），保持自包含
- [x] **Retriever**（`capabilities/retriever.py`）：grounding 接入 plan / compile / pedagogy；零依赖 `SimpleRetriever`（snippet / 本地文件 + 关键词排序）；LlamaIndex 为可选 `[rag]` extra
- [x] CLI `--ground <file>`（可重复）注入 grounding；engine 新增 ③ Retrieve 阶段
- [x] 块级单元 + 渲染回归测试（`tests/test_blocks.py` 参数化覆盖全部 13 类 + 真实浏览器零 console 错误验证）
- [ ] **顺延**：React 单组件 target（`render_target="react"`）+ 渲染器（需构建环境，与「自包含单文件」原则有张力，单独评估）
- [ ] **顺延**：LlamaIndex 向量检索 adapter 实装（接口已留）

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
