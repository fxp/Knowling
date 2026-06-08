# 借鉴分析：get-it / cell-architecture-studio → Knowling

> 任务：分析 [beltromatti/get-it](https://github.com/beltromatti/get-it) 与
> [cclank/cell-architecture-studio](https://github.com/cclank/cell-architecture-studio)
> 的「课程/内容生成」部分，挑选适合 Knowling 的零件。
>
> 结论先行：**两个项目的主体方向都与 Knowling 的 focus 相悖，不应整体照搬。**
> 但各自有 1–2 个零件天然落在「单知识点学习 + Quiz」范围内，值得吸收。

---

## 0. 判断基准：Knowling 的不变量

任何借鉴都必须同时满足这三条，否则破坏护城河：

1. **单知识点（single KP）**——不做多概念拆解、不做跨概念知识图谱/导航、不做整课。
   （ROADMAP 已把 P3「拆解+导航」✂︎ 移出范围。）
2. **自包含单文件、零运行时依赖**——产物是一个内联 CSS/JS 的 `.html`，无外部 CDN/字体/框架。
3. **可质检**——块要能产出 `qa_assertions`，过三维质检（渲染/交互/教学）才标 `ready`。

---

## 1. 三方定位对比

| | 它做什么 | 技术栈 | 与 Knowling 的关系 |
|---|---|---|---|
| **Knowling**（本项目） | 单知识点 → 自包含单 HTML 学习卡 + Quiz；13 类块；Spec-first；三维质检 | Python，零依赖核心 | 基准 |
| **get-it** | PDF → 概念检测 → 逐概念可视化 → **跨概念知识图谱** → 四学习工具 + 四轴掌握度评分 | Next.js 16 / React 19 / Electron / Three.js / 自带 ChatGPT(Codex CLI) | 整体是「整本资料 → 课程化学习系统」，**主体出范围** |
| **cell-architecture-studio** | 预制的 7 种 3D 细胞标本画廊 + AI Tutor 面板 + 视觉验证脚本 | React 19 / Vite / Three.js / R3F / Drei | **不是生成管线**，是成品内容站，可借的极少 |

---

## 2. get-it 逐零件评估

get-it 的管线：`概念检测 → 可视化渲染 → 知识图谱构建 → 评估`，外加四个学习工具（Chat / Flashcards / Quizzes / **Feynman**）汇入一个 journal。

| 零件 | 说明 | 是否可借 | 理由 |
|---|---|---|---|
| **Feynman 工具** | 以「学生」身份向学习者提出解释性追问，逼出主动输出 | ✅ **强烈推荐** | 纯单 KP；是 flashcards/quiz 之外缺失的「输出式/费曼学习」环节；可做成自包含块（预生成苏格拉底追问 + 自评），或 Studio 层的活体对话 |
| **四轴掌握度评分** | memory / comprehension / structure / application 四轴，单调不降（只进不退） | 🟡 可改造 | 原设计是「跨概念 journal」的属性（出范围）；但四轴模型本身可降维成**单卡内的掌握度自评**，或并入 pedagogy 质检维度作教学评分锚点 |
| **客户端 spec 修复环（repair loop）** | 逐 tag 可视化 spec 生成失败时本地重试修复 | ⏸ 已具备 | Knowling 的 `qa/loop.py`（回溯+选优+只重编译失败块）已是同类机制，无需引入 |
| **概念检测（batched agent，≤5 页/次）** | 从 PDF 多页抽取概念 + 锚点串 | ❌ 出范围 | 这是「多概念拆解」，正是移出的 P3 |
| **知识图谱合成（6–25 节点 + 类型化边）** | 构建概念关系图并增量评估 | ❌ 出范围 | 跨概念导航，明确不做 |
| **PDF 文本/字形抽取（pdfjs-dist）** | 上传 PDF → 提取文本与 bbox | ❌ 出范围 | 输入是「整本资料」，与「输入一个细小知识点」相悖；如需 grounding，已有 `retriever.py --ground` |
| **Bring-your-own-ChatGPT / Codex CLI 作认证传输** | 复用用户 ChatGPT 订阅，无服务端计费 | ❌ 不相关 | Provider 选型问题；Knowling 走 GLM/zhipu，且 provider 已抽象可插拔 |
| **统一 journal（单 JSON 可下载）** | 跨工具学习记录 | ❌ 出范围 | 跨概念/跨会话的学习档案，属宿主系统职责 |

---

## 3. cell-architecture-studio 逐零件评估

| 零件 | 说明 | 是否可借 | 理由 |
|---|---|---|---|
| **3D 模型作为一种模态** | Three.js/R3F 渲染可选器官的 3D 模型 | 🟡 弱契合 | 你刚加了 audio 模态，3D 是顺理成章的下一个模态块（`model_3d`）。但 Three.js 较重，**必须内联**才不破坏零依赖，与「自包含单文件」有真实张力；建议先评估体积/降级方案 |
| **AI Tutor 面板** | 侧边栏教学引导对话 | ⏸ 已具备 | Knowling Studio 层（`studio.py`/`serve`/`refine`）已提供卡外 AI 聊天改写层 |
| **`scripts/verify.mjs` 视觉验证** | Playwright 截图回归 | ⏸ 已具备 | Knowling `sandbox/` + `qa/render_vlm` 已覆盖渲染质检 |
| **预制细胞内容 / GLB 资产** | 7 种成品标本数据 | ❌ 不相关 | 是内容，不是生成逻辑 |

> 一句话：cell-architecture-studio 是「成品展示站」而非「生成管线」，对 Knowling 的生成内核几乎没有可迁移的逻辑，唯一价值是「3D 模态」这个**想法**。

---

## 4. 推荐落地清单（按契合度排序）

### ① Feynman 块（最佳，建议优先）
- **来源**：get-it 的 Feynman 工具。
- **形态**：新增 `feynman` 块，自包含。内容 spec 形如
  `{ prompts: [{question, hint?, model_answer}], self_assess: true }`：
  展示一组「以学生口吻」的追问，学习者先自己作答/口述，再翻看 model answer 并自评（答上来 / 卡住）。
- **为什么契合**：纯单 KP；补齐「主动输出 / 费曼复述」这一现有块缺失的学习环节；零依赖；
  `qa_assertions` 可校验「可逐题展开 + 可自评」。
- **成本**：低。复用 flashcards 的翻面/分步交互范式。

### ② 四轴掌握度自评
- **来源**：get-it 四轴评分（memory/comprehension/structure/application，单调不降）。
- **两种落法**（择一）：
  - **(a) 块**：单卡末尾一个掌握度自评条，四轴各一档，学习者自评，状态存 localStorage（仍自包含）。
  - **(b) 质检维度**：把四轴作为 `pedagogy_judge` 的评分锚点，使教学分更结构化。
- **为什么契合**：四轴模型可干净地降维到单 KP；(b) 还能直接强化护城河（质检）。
- **成本**：中。

### ③ 3D 模型模态块（可选，最弱）
- **来源**：cell-architecture-studio 的 Three.js 模态。
- **形态**：`model_3d` 块，内联精简版 Three.js + 一个 `.glb`/程序化几何体，可旋转/选器官。
- **顾虑**：Three.js 体积大、内联与零依赖原则张力大；需先定降级路径（无 WebGL → 静态图）。
- **建议**：作为「模态扩展」单独立项评估，不与 ①② 捆绑。

---

## 5. 明确不借（避免范围漂移）

- 概念检测 / 多页拆解 / 知识图谱合成 / 跨概念导航（get-it）——等于复活已砍的 P3。
- PDF 整本抽取作输入（get-it）——与「输入一个细小知识点」相悖。
- 跨工具/跨会话 journal（get-it）——属宿主系统，不进本模块。
- 预制 3D 内容与成品站结构（cell）——是内容不是逻辑。

---

## 6. 一句话总结

> 这两个项目的「课程生成」主体（多概念拆解、知识图谱、整本 PDF 输入）**恰恰是 Knowling 主动放弃的方向**，照搬会破坏 focus。真正值得吸收的是落在单知识点边界内的**学习交互零件**：首推 **Feynman 块**（输出式学习），其次 **四轴掌握度自评**（可并入质检），3D 模态作为可选的模态扩展单独评估。
