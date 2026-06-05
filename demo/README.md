# Knowling 演示画廊

一个自包含的画廊页，展示 Knowling 生成的「单知识点学习 + Quiz」卡片。

## 查看

直接用浏览器打开 [`index.html`](index.html)（无需服务器）。每张卡片内嵌一个**可交互**、卡片牌组式（一次一张）的预览，点「在新标签打开」可全屏体验。

## 内容

跨学科示例，均由真实 GLM-5 规划内容、统一模板渲染、通过三维质检：

- **正弦函数 y = A·sin(ωx + φ)** — param_sim 曲线随 A/ω/φ 滑块变化
- **二次函数顶点式 y = a(x−h)²+k** — 抛物线随系数平移/开口
- **二分查找 Binary Search** — step_through 逐步推演
- **复利 A = P(1+r)ⁿ** — 指数增长 + Quiz

## 重新生成

```bash
# 渲染画廊（从 examples.json + 组件文件，无需模型）
python3 demo/build.py

# 重新生成组件（需要 GLM key；无 key 则用离线模板）
export ZHIPU_API_KEY=...
python3 demo/build.py --generate
```

要改示例列表：编辑 `demo/build.py` 顶部的 `EXAMPLES`，再 `--generate`。

## 对话式改写

画廊里的卡片是确定状态。想边看边改，用 Studio：

```bash
export ZHIPU_API_KEY=...
python3 -m knowling.cli serve "正弦函数" --objectives "理解A/ω/φ的作用"
# 左边卡片，右边 AI 聊天：说「太难了」「讲深点」「和余弦的关系」即重新生成换卡（自带不跑题守卫）。
```
