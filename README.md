# Knowling

输入一个**细小、明确的知识点**，输出一个自包含、可交互的高质量学习组件（Knowling）。

> 完整设计见 [`knowling-design.md`](knowling-design.md)。本仓库当前实现 **P0 骨架**。

## P0 已实现（设计文档 §12）

跑通最小闭环 **`知识点 → 蓝图(KnowlingSpec) → 块编译 → 自包含 HTML`**：

- **Spec-first 管线**（`knowling/engine.py`）：Plan → Approval(auto) → Compile → Assemble，每阶段发出进度事件。
- **KnowlingSpec 蓝图层**（`knowling/schema/`）：唯一可审阅 / diff 的中间表示（approval gate）。
- **3 个块**（`knowling/blocks/`）：`text` / `quiz` / `param_sim`（滑块驱动、canvas 可视化的 explorable）。未实现的块类型回退到 `generic` 占位，不会让管线崩溃。
- **Provider 抽象**（`knowling/providers/`）：默认 GLM/zhipu（`glm-4.6`），无 API key 时自动回退离线 **MockProvider**，开箱即跑。
- **CLI 双输出**（`knowling/cli.py`）：`-f rich`（人）/ `-f json`（agent 事件流）。
- **自包含产物**：单个 `.html`，内联 CSS/JS，无外部运行时依赖。

尚未实现（后续阶段）：① 大主题拆解、③ RAG grounding、⑤ 三维质检闭环、全 13 类块、React target、Server API。

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
├── engine.py            # L3 编排: generate_knowling()
├── capabilities/        # spec_planner, block_compiler
├── blocks/              # 块注册表: text / quiz / param_sim / generic
├── providers/           # LLM 抽象: zhipu(GLM) + mock + factory
├── schema/              # KnowledgePoint / KnowlingSpec / Knowling
├── assembler.py         # 块片段 → 单文件自包含 HTML
└── cli.py               # 双输出 CLI
tests/
├── test_pipeline.py
└── golden_specs/        # 蓝图回归夹具
```
