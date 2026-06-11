# Knowling

输入一个**细小、明确的知识点**，输出一个自包含、可交互的高质量学习组件（Knowling）。

**范围（精炼 focus）**：只做「单个知识点的学习 + Quiz」组件——叙述 + explorable 演示 + 测验。**不做**大主题拆解、知识图谱导航、整课/整书生成。

> 完整设计见 [`knowling-design.md`](knowling-design.md)，开发进度见 [`ROADMAP.md`](ROADMAP.md)。
>
> **演示画廊**：用浏览器打开 [`demo/index.html`](demo/index.html) 即可交互体验生成的组件——含真实 GLM-5 生成的「正弦函数 / 二次函数 / 二分查找 / 复利」，以及参考 [HarleyCoops/Math-To-Manim](https://github.com/HarleyCoops/Math-To-Manim) 与 3Blue1Brown 可视化手写蓝图的 **Math-To-Manim 系列**（傅里叶级数逼近方波、泰勒级数逼近 eˣ、圆面积展开法）。

## 已实现（P0 + P1 + P2，设计文档 §12）

跑通完整闭环 **`知识点 →(RAG grounding)→ 蓝图(KnowlingSpec) → 块编译 → 四维质检 → 自包含 HTML`**：

**P0 骨架**
- **Spec-first 管线**（`knowling/engine.py`）：Retrieve → Plan → Approval(auto) → Compile → QA → Assemble，每阶段发出进度事件。
- **KnowlingSpec 蓝图层**（`knowling/schema/`）：唯一可审阅 / diff 的中间表示（approval gate）。
- **全 13 类块**（`knowling/blocks/`）：`text` `callout` `figure` `code` `section` `quiz` `flashcards` `timeline` `concept_graph` `interactive_demo` `param_sim` `step_through` `animation` `deep_dive` `user_note`，均自包含、带 `qa_assertions`；未知类型回退 `generic` 占位。
- **Provider 抽象**（`knowling/providers/`）：默认 GLM/zhipu（`glm-4.6`），无 API key 时自动回退离线 **MockProvider**，开箱即跑。
- **CLI 双输出**（`knowling/cli.py`）：`-f rich`（人）/ `-f json`（agent 事件流）。
- **自包含产物**：单个 `.html`，内联 CSS/JS，无外部运行时依赖。

**P1 质检闭环**（护城河，扩展自 WebGen-Agent）
- **沙箱**（`knowling/sandbox/`）：Playwright headless Chromium 渲染+截图+console 捕获；无浏览器时自动回退 `StaticSandbox`，QA 仍可离线跑。
- **四维质检**（`knowling/capabilities/qa/`）：① 渲染分（GLM-4V / 启发式）→ ② 交互分（校验块 `qa_assertions`）→ ③ 教学分（强 LLM 锚定 Explorable Explanations）→ ④ **可学会分**（强 LLM 模拟一名已掌握全部前置知识的学习者，**只读卡片内容**，逐条判定每个学习目标所需的知识能否由卡片本身获得；常识但卡片没讲出来的不算）。按序短路，便宜的先跑。
- **回溯 + 选优 + 重编译失败块**（`qa/loop.py`）：连续渲染报错回退最佳前序；选优 learn→peda→interact→render→recency；只重编译失败块并注入质检建议（含可学会维指出的「缺什么」）。
- **状态闸门**：四维全过才标 `status="ready"`，否则 `qa_failed`（未过质检不得 ready）。`--no-qa` 可跳过（停留 `draft`）。

**P2 全块 + RAG**
- **全 13 类块**实现完毕（重心 `step_through` / `interactive_demo`；`concept_graph` 用内联 canvas 保持自包含）。
- **RAG grounding**（`knowling/capabilities/retriever.py`）：零依赖 `SimpleRetriever`（snippet / 本地文件 + 关键词排序），grounding 注入 plan / compile / 教学评审。CLI `--ground <file>`（可重复）。

**数学公式渲染（自包含）**
- LaTeX（`$…$` / `\frac` / `\omega` …）默认走**编译期 Temml → 原生 MathML** 内联（完整覆盖、运行时零 JS/零字体），无 Node/Temml 时自动回退纯 Python 子集渲染器（`KNOWLING_MATH=fallback` 可强制）。Temml 已 vendored（MIT，build-time only，不进产物）。

尚未实现（后续阶段）：① 大主题拆解、知识图谱导航外壳、React target、Server API、模型驱动 GUI agent、LlamaIndex 向量检索。

## 快速开始

```bash
# 零依赖、零 API key 即可跑（自动用 MockProvider）
python3 -m knowling.cli gen "链式法则" \
  --objectives "能对复合函数求导,能解释为何相乘" \
  --difficulty core --audience "高中生" -o ./out/

# 接入真实 GLM
export ZHIPU_API_KEY=sk-...
python3 -m knowling.cli gen "傅里叶变换的频率含义" -o ./out/

# 仅出蓝图 → 审阅 → 编译
python3 -m knowling.cli plan "梯度下降" -o ./out/gd.spec.json
python3 -m knowling.cli compile ./out/gd.spec.json --title "梯度下降" -o ./out/gd.html

python3 -m knowling.cli blocks          # 列出块类型
```

### AI Chat / Studio（学习卡之外的改写层）

每张学习卡是一个**确定状态**（自包含 HTML，不内嵌 chat）。Studio 在卡片之外提供一个 AI 聊天层：输入当前卡内容 + 你的诉求 → 生成一张新卡。

```bash
export ZHIPU_API_KEY=...
python3 -m knowling.cli serve "链式法则" --objectives "能对复合函数求导" --audience 高中生
# 浏览器打开 → 左边学习卡，右边聊天。说「太难了」「讲深点」「和导数的关系」即重新生成换卡。

# 或命令行单次改写：
python3 -m knowling.cli refine ./out/gd.spec.json "太难了，给初中生版本" --title 梯度下降 -o ./out/gd2.html
```

安装为命令（可选）：`pip install -e .` 后可直接用 `knowling gen ...`。

### HTTP API（供宿主/Agent 调用）

零依赖 stdlib HTTP 服务，把引擎暴露为 JSON 接口（见 [`docs/api.md`](docs/api.md)）：

```bash
export ZHIPU_API_KEY=...                 # 可选；无 key 自动走离线 Mock
python3 -m knowling.server --port 8765   # 或装包后：knowling-api --port 8765
# POST /v1/{plan,generate,compile,refine,reteach,quiz-eval} · GET /v1/{health,blocks}
```

`generate` 直接返回自包含 HTML（`html` 字段）；`quiz-eval` 把测验结果转成掌握度信号（点亮图谱用）。

## 测试

```bash
python3 -m pytest tests/ -q
```

## 目录

```
knowling/
├── engine.py            # L3 编排: generate_knowling() / compile_spec()
├── capabilities/
│   ├── spec_planner.py  # 知识点 → 蓝图
│   ├── block_compiler.py# 蓝图块 → 自包含 HTML 片段
│   └── qa/              # 四维质检: render_vlm / gui_agent / pedagogy_judge / learn_judge / loop
├── sandbox/             # 渲染沙箱: playwright + static 回退
├── blocks/              # 块注册表: text / quiz / param_sim / generic (+qa_assertions)
├── providers/           # LLM 抽象: zhipu(GLM) + mock + factory
├── schema/              # KnowledgePoint / KnowlingSpec / Knowling
├── assembler.py         # 块片段 → 单文件自包含 HTML
└── cli.py               # 双输出 CLI
tests/
├── test_pipeline.py     # 端到端闭环
├── test_qa.py           # 质检维度 / 选优 / 回溯
└── golden_specs/        # 蓝图回归夹具
```

可选：真实浏览器质检 `pip install -e ".[qa]" && python3 -m playwright install chromium`（缺省走 static 沙箱）。
