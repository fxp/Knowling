# Knowling 演示画廊

一个自包含的画廊页，展示 Knowling 生成的「单知识点学习 + Quiz」组件。

## 查看

直接用浏览器打开 [`index.html`](index.html)（无需服务器）。每张卡片内嵌一个**可交互**的组件预览，点「在新标签打开」可全屏体验。

## 内容

- **GLM-5 生成**：`正弦函数 y = A·sin(ωx + φ)` — 由真实 GLM-5 规划 + 编译，并通过三维质检（渲染/交互/教学）。
- **离线模板**：`链式法则`、`欧姆定律 V=IR` — 由 MockProvider 无 API key 生成，展示管线结构。

## 重新生成

```bash
python3 demo/build.py
```

该脚本会：
1. 用离线 MockProvider 生成示例组件到 `components/`；
2. 若存在 `out/sine-real.html`（真实 GLM 产物）则一并纳入；
3. 渲染 `index.html` 画廊与 `manifest.json`。

要新增一个真实 GLM 示例：

```bash
export ZHIPU_API_KEY=...
python3 -m knowling.cli gen "你的知识点" --description "..." --objectives "..." -o ./out/your.html
# 然后在 build.py 的 _fold_real 里加入该文件，或扩展脚本
```
