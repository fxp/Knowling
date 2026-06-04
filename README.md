# Knowling

输入一个**细小、明确的知识点**，输出一个自包含、可交互的高质量学习组件（Knowling）。

> 完整设计见 [`knowling-design.md`](knowling-design.md)。本仓库当前实现 **P0 骨架**。

## 已实现（P0 + P1，设计文档 §12）

跑通完整闭环 **`知识点 → 蓝图(KnowlingSpec) → 块编译 → 三维质检 → 自包含 HTML`**：

**P0 骨架**
- **Spec-first 管线**（`knowling/engine.py`）：Plan → Approval(auto) → Compile → QA → Assemble，每阶段发出进度事件。
- **KnowlingSpec 蓝图层**（`knowling/schema/`）：唯一可审阅 / diff 的中间表示（approval gate）。
- **3 个块**（`knowling/blocks/`）：`text` / `quiz` / `param_sim`（滑块驱动、canvas 可视化的 explorable）。未实现的块类型回退到 `generic` 占位，不会让管线崩溃。
- **Provider 抽象**（`knowling/providers/`）：默认 GLM/zhipu（`glm-4.6`），无 API key 时自动回退离线 **MockProvider**，开箱即跑。
- **CLI 双输出**（`knowling/cli.py`）：`-f rich`（人）/ `-f json`（agent 事件流）。
- **自包含产物**：单个 `.html`，内联 CSS/JS，无外部运行时依赖。

**P1 质检闭环**（护城河，扩展自 WebGen-Agent）
- **沙箱**（`knowling/sandbox/`）：Playwright headless Chromium 渲染+截图+console 捕获；无浏览器时自动回退 `StaticSandbox`，QA 仍可离线跑。
- **三维质检**（`knowling/capabilities/qa/`）：① 渲染分（GLM-4V / 启发式）→ ② 交互分（校验块 `qa_assertions`）→ ③ 教学分（强 LLM 锚定 Explorable Explanations）。按序短路，便宜的先跑。
- **回溯 + 选优 + 重编译失败块**（`qa/loop.py`）：连续渲染报错回退最佳前序；选优 peda→interact→render→recency；只重编译失败块并注入质检建议。
- **状态闸门**：三维全过才标 `status="ready"`，否则 `qa_failed`（未过质检不得 ready）。`--no-qa` 可跳过（停留 `draft`）。

尚未实现（后续阶段）：① 大主题拆解、③ RAG grounding、全 13 类块、React target、Server API、模型驱动 GUI agent。

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

安装为命令（可选）：`pip install -e .` 后可直接用 `knowling gen ...`。

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
│   └── qa/              # 三维质检: render_vlm / gui_agent / pedagogy_judge / loop
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
