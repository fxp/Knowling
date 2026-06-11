# Knowling 演示画廊

一个自包含的画廊页，展示 Knowling 生成的「单知识点学习 + Quiz」卡片。

## 查看

直接用浏览器打开 [`index.html`](index.html)（无需服务器）。每张卡片内嵌一个**可交互**、卡片牌组式（一次一张）的预览，点「在新标签打开」可全屏体验。

## 内容

跨学科示例，统一模板渲染、通过三维质检。徽章标注内容来源：

**GLM-5 规划**
- **正弦函数 y = A·sin(ωx + φ)** — param_sim 曲线随 A/ω/φ 滑块变化
- **二次函数顶点式 y = a(x−h)²+k** — 抛物线随系数平移/开口
- **二分查找 Binary Search** — step_through 逐步推演
- **复利 A = P(1+r)ⁿ** — 指数增长 + Quiz

**Math-To-Manim 系列**（手写蓝图，灵感来自 [HarleyCoops/Math-To-Manim](https://github.com/HarleyCoops/Math-To-Manim) 与 3Blue1Brown 的可视化）
- **傅里叶级数逼近方波** — 滑块加入奇次谐波，看方波浮现 + 吉布斯过冲
- **泰勒级数逼近 eˣ** — 滑块控制项数，多项式逐段咬住 e^x（收敛半径）
- **圆面积 A = πr²（展开法）** — 同心环拉直叠成三角形，不用积分推出 πr²

**精选 Explorable**（用最新引擎手写蓝图：每张以「前置知识」开场，四维质检 5/5/5/5 全过）
- **导数：切线的斜率 f′(x₀)** — 移动切点看切线转动，斜率读数恒为 2x₀
- **抛体运动：射程与最大高度** — 滑动发射角，看射程在 45° 达峰、互补角射程相同
- **阻尼振动 A·e⁻ᵞᵗcos(ωt)** — 振荡被一对指数包络夹住收口，阻尼 γ 控制衰减
- **对数函数 y=logₐx 与底数 a** — 曲线恒过 (1,0)，在 x=a 处穿过 y=1

> Math-To-Manim 系列与精选 Explorable 均为**手写的 KnowlingSpec 蓝图**（见 `demo/specs/`），
> 用同一套 `.kl-*` 模板编译，可用 `python3 demo/build.py --rerender` **免模型**从蓝图重新编译。

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
