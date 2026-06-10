---
name: knowling
description: 为单个细小知识点生成自包含、可交互的精品学习组件（Knowling）。当用户说「给这个知识点做个可交互组件」「把XX讲清楚做成可玩的演示」「生成一个 explorable 学习卡片」「knowling」或类似表达时触发。SKIP 整门课程/整本书生成、纯静态文章写作。
---

# Knowling — 知识点 → 可交互学习组件

> 📦 **可安装的技能定义在 [`.claude/skills/knowling/SKILL.md`](.claude/skills/knowling/SKILL.md)**（项目技能，随仓库分发）。本文件是项目层的说明文档。

输入**一个细小、明确的知识点**，输出一个经过结构化蓝图规划、自包含（单文件、无外部依赖）的可交互学习组件。完整闭环 `知识点 → 蓝图(KnowlingSpec) → 块编译 → 四维质检(QA) → 自包含 HTML`：13 类块（含 `param_sim`/`step_through`/`audio`/3B1B 风格 `manim` 动画）、RAG grounding、答错重教、HTTP API 均已实现。

## 何时触发
- 用户给出一个具体知识点（如「链式法则」「TCP 三次握手」「二次函数系数 a 的作用」）并希望得到可交互的学习产物。
- 优先做 `param_sim`（滑块驱动模拟）/ `step_through` / `interactive_demo` 这类「动手改变某个量并观察结果」的 explorable 组件。

## 如何调用（CLI，双输出）

```bash
# 完整闭环：plan → compile → assemble，产出单个 .html
python3 -m knowling.cli gen "链式法则" \
  --objectives "能对复合函数求导,能解释为何相乘" \
  --difficulty core --audience "高中生" \
  --format-render html -o ./out/

# 带 RAG grounding（本地文件，可重复 --ground 锚定事实，防幻觉）
python3 -m knowling.cli gen "欧姆定律" --description "V=IR" --ground ./notes/ohm.md -o ./out/

# 仅产蓝图给人/agent 审阅（不编译）
python3 -m knowling.cli plan "梯度下降" -o ./out/gd.spec.json

# 从审批后的蓝图编译
python3 -m knowling.cli compile ./out/gd.spec.json --title "梯度下降" -o ./out/gd.html

# 列出已实现 / 已声明的块类型
python3 -m knowling.cli blocks

# 用一句话诉求改写一张卡 → 生成新卡（学习卡之外的 AI 改写层）
python3 -m knowling.cli refine ./out/gd.spec.json "太难了，给初中生版本" --title 梯度下降 -o ./out/gd2.html

# Knowling Studio：左边学习卡 + 右边 AI Chat，对话式改写并实时换卡
python3 -m knowling.cli serve "链式法则" --objectives "能对复合函数求导" --audience 高中生
```

## AI Chat / Studio（学习卡之外的改写层）
- 每张学习卡是一个**确定状态**（自包含、不内嵌 chat）。`refine` / Studio 把「当前卡的 spec + 用户诉求」喂给模型，**生成一张新卡**。
- 诉求示例：「太难了」「讲深点」「举个例子」「和导数是什么关系？」。
- `knowling serve` 启动本地 Studio（key 留在服务端）：左侧卡片、右侧聊天 + 快捷诉求；发消息即重新生成、重跑质检、换卡。
- 编程接口：`engine.refine_knowling(spec, kp, instruction, cfg) -> (new_knowling, summary)`。
- **保真守卫（不跑题）**：改写后用 `fidelity` 检查卡片是否仍聚焦本知识点；若跑题（如「和X的关系」把卡片变成讲 X）→ 强化约束重试，仍跑题则回退到「只加澄清块、主体不动」。质检教学维也加入了「是否跑题」准则。Studio 会显示「· 已保持聚焦本知识点 ✓」。

**输出模式**（仿 DeepTutor）：
- `-f rich`（默认）：彩色人类可读进度。
- `-f json`：行分隔 JSON 事件流（`stage` / `cost` / `done` / `info`），供 agent 解析进度、成本、最终 Knowling 对象。

## Provider（模型层）
- 默认 `--provider auto`：检测到 `ZHIPU_API_KEY` / `GLM_API_KEY` 则走 GLM（zhipu，`glm-5.1` + 视觉 `glm-5v-turbo`），否则自动回退到离线 **MockProvider**（零成本，开箱即跑）。

## 渲染一致性（`--compile-mode`）
- **`template`（默认）**：GLM 负责**规划内容**（KnowlingSpec），所有已知块用统一的 `.kl-*` 设计系统**模板渲染** → 组件风格一致、可靠、便宜。这是「知识点学习+Quiz 组件」的推荐路径。
- **`codegen`**：GLM 为每块直接写 HTML/JS（视觉更多样，但风格不一致、偶有破损）。仅在需要模板未覆盖的新型交互时使用。
- 产物为**知识卡片牌组**：一个块一张卡，用户一次只看一张，上一张/下一张/圆点导航。

## KnowlingSpec 摘要（审批门 / 唯一可 diff 层）
```
{ knowledge_point_id, pedagogy:{hook, central_phenomenon, misconceptions[], aha_moment},
  blocks:[ { block_id, type, intent, content_spec, interaction_spec? } ],
  render_target:"html"|"react", version }
```
全部 13 类块均已实现（`text` `callout` `figure` `code` `section` `quiz` `flashcards` `timeline` `concept_graph` `interactive_demo` `param_sim` `step_through` `animation` `deep_dive` `user_note`），content_spec 见设计文档 §7。常用：
- `text`     → `{ md }`
- `quiz`     → 单题 `{ question, options[], answer:int, explain }`；或多题测验 `{ title?, questions:[{type,prompt,...,explain}] }`，type ∈ `single`/`multi`(answer:int[])/`boolean`(answer:bool)/`fill`(answer:str, accept?:str[])，多题自动计分+重做
- `param_sim`→ `{ params:[{name,label,min,max,step,default}], outputs:[{name,label,expr}], explain }`（`expr` 是关于 param 名的 JS 表达式，如 `"x*x"`）
- `interactive_demo` → `{ controls:[{name,label,kind}], outputs:[{name,label,expr}] }`（kind ∈ slider/number/select/checkbox/text）
- `step_through` → `{ steps:[{state,explain}] }`

## 风格档（后续）
计划提供 `knowling-minimal` / `knowling-rich-explorable` / `knowling-exam-prep` 多风格 skill，通过 triggers 区分。P0 暂为单一默认风格。

## 质检（P1，已接入）
- `gen` / `compile` 默认跑四维质检闭环：渲染分 → 交互分 → 教学分 → 可学会分（模拟已掌握前置知识的学习者，只读卡片就能获得该知识点所需知识），四维全过才标 `status="ready"`，否则 `qa_failed`。
- 沙箱优先用 Playwright（真实浏览器截图+console），缺省自动回退结构化静态沙箱（仍可离线跑）。
- `--no-qa` 跳过质检（产物停留 `draft`）；QA 进度/分数进入 rich/json 事件流。

## 数学公式（自包含，无 CDN）
- GLM 写的 `$...$` / `\frac` / `\omega` 等会被渲染：默认用**编译期 Temml → 原生 MathML** 内联（完整 LaTeX 覆盖、运行时零 JS/零字体），检测不到 Node/Temml 时**自动回退**到纯 Python 子集渲染器。
- `KNOWLING_MATH=fallback` 可强制用回退渲染器。Temml 为可选 build-time 工具（已 vendored，MIT），不进产物。

## 注意
- 未过质检不得标 `ready`（设计文档 §3.1）。
- 编译产物为单个自包含 `.html`，可直接嵌入/分发。
