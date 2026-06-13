#!/usr/bin/env python3
"""Build the Knowling demo gallery.

Two modes:
  python3 demo/build.py --generate   # (re)generate example components via the
                                      # configured provider (GLM if a key is set,
                                      # else offline mock) and write examples.json
  python3 demo/build.py              # render demo/index.html from examples.json
                                      # + the committed component files (no model)

Open: demo/index.html
"""

from __future__ import annotations

import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COMPONENTS = os.path.join(HERE, "components")
SPECS = os.path.join(HERE, "specs")
MANIFEST = os.path.join(HERE, "examples.json")
sys.path.insert(0, ROOT)

# ── the example knowledge points (diverse subjects + blocks) ──────────
EXAMPLES = [
    {"id": "sine_function", "title": "正弦函数 y = A·sin(ωx + φ)",
     "description": "振幅A、角频率ω、相位φ 各自如何改变正弦波形",
     "objectives": "理解A控制振幅,ω控制周期,φ控制水平平移",
     "audience": "高一学生", "difficulty": "core"},
    {"id": "quadratic_vertex", "title": "二次函数顶点式 y = a(x−h)² + k",
     "description": "系数 a、顶点坐标 (h, k) 如何决定抛物线的形状与位置",
     "objectives": "理解a控制开口与宽窄,h控制左右平移,k控制上下平移",
     "audience": "初中生", "difficulty": "core"},
    {"id": "binary_search", "title": "二分查找 Binary Search",
     "description": "在有序数组中通过不断对半缩小区间来定位目标值",
     "objectives": "理解每步如何排除一半元素,掌握 low/high/mid 的更新",
     "audience": "编程初学者", "difficulty": "core"},
    {"id": "compound_interest", "title": "复利 A = P(1 + r)ⁿ",
     "description": "本金P、利率r、期数n 如何共同决定最终金额，以及复利与单利的差异",
     "objectives": "理解复利随期数指数增长,体会利率与时间的威力",
     "audience": "理财入门", "difficulty": "intro"},
    {"id": "bayes_theorem", "title": "贝叶斯定理：证据如何更新信念",
     "description": "先验P(D)、似然P(+|D)、后验P(D|+) 三者如何随证据更新，及基础率忽视",
     "objectives": "分清似然与后验,理解先验如何影响后验,看懂后验公式",
     "audience": "初学者", "difficulty": "core"},
    {"id": "normal_distribution", "title": "正态分布：μ 与 σ 如何决定钟形曲线",
     "description": "均值μ控制位置、标准差σ控制胖瘦与峰高，曲线下面积恒为1",
     "objectives": "理解μ控制位置,理解σ控制分散与峰高,理解面积守恒为1",
     "audience": "统计入门", "difficulty": "core"},
    {"id": "exponential_decay", "title": "指数衰减与半衰期 N = N₀·(1/2)^(t/T)",
     "description": "半衰期T与初始量N₀如何决定衰减曲线，每过一个T剩余量减半且永不为0",
     "objectives": "理解每过半衰期减半,理解T控制衰减快慢,区分指数衰减与线性减少",
     "audience": "高中生", "difficulty": "intro"},
    {"id": "sigmoid_function", "title": "Sigmoid 函数 σ(x)=1/(1+e^(−k(x−x₀)))",
     "description": "陡峭度k控制S形软硬、中点x₀控制平移，输出恒被挤压在(0,1)",
     "objectives": "理解输出恒在0到1之间,理解k控制陡缓,理解x₀控制中点位置",
     "audience": "机器学习入门", "difficulty": "core"},

    # ── Math-To-Manim 系列（手写蓝图，灵感来自 HarleyCoops/Math-To-Manim
    #    与 3Blue1Brown 的可视化；用 --rerender 从 demo/specs 免模型重编译）──
    {"id": "fourier_square_wave", "title": "傅里叶级数逼近方波",
     "description": "用频率成倍、振幅递减的奇次正弦波叠加出方波，以及吉布斯过冲现象",
     "objectives": "理解方波只含奇次谐波,谐波越多越逼近,认识吉布斯现象",
     "audience": "本科生", "difficulty": "advanced", "source": "Math-To-Manim"},
    {"id": "taylor_series_exp", "title": "泰勒级数逼近 eˣ",
     "description": "用多项式部分和逼近 e^x，项数越多逼近范围越大，以及收敛半径的含义",
     "objectives": "理解麦克劳林展开,阶乘分母保证收敛,区分收敛半径有限/无穷",
     "audience": "高中/本科", "difficulty": "advanced", "source": "Math-To-Manim"},
    {"id": "circle_area", "title": "圆面积 A = πr²（展开法）",
     "description": "把圆拆成同心环、拉直叠成三角形，不用积分推出 πr²，并体会平方关系",
     "objectives": "理解几何推导,掌握面积随半径平方增长,区分周长与面积公式",
     "audience": "初中生", "difficulty": "core", "source": "Math-To-Manim"},

    # ── 精选 Explorable（最新引擎手写蓝图：前置知识页 + 四维质检全过 5/5/5/5）──
    {"id": "derivative_tangent", "title": "导数：切线的斜率 f′(x₀)",
     "description": "在 y=x² 上移动切点 x₀，切线随之转动，斜率读数恒等于 f′(x₀)=2x₀",
     "objectives": "把导数理解为切线斜率,认识导数是随位置变化的函数,区分割线与切线",
     "audience": "高中生", "difficulty": "core", "source": "精选"},
    {"id": "projectile_motion", "title": "抛体运动：射程与最大高度",
     "description": "发射角θ与初速v₀如何决定抛物线轨迹，为何45°射程最大、互补角射程相同",
     "objectives": "理解轨迹是抛物线,掌握射程R∝sin2θ在45°最大,区分最远与最高",
     "audience": "高中生", "difficulty": "core", "source": "精选", "featured": True},
    {"id": "damped_oscillation", "title": "阻尼振动 A·e⁻ᵞᵗcos(ωt)",
     "description": "余弦振荡乘指数衰减包络，阻尼γ决定衰减快慢，振幅按比例而非等量缩小",
     "objectives": "把阻尼振动拆成振荡×衰减,理解包络夹住振荡,区分比例衰减与线性衰减",
     "audience": "高中/本科", "difficulty": "advanced", "source": "精选"},
    {"id": "logarithm_base", "title": "对数函数 y=logₐx 与底数 a",
     "description": "对数是指数的反函数，所有曲线过(1,0)且在x=a处取1，底数越大越平缓",
     "objectives": "把对数理解为指数的反问,掌握logₐa=1的几何意义,认清定义域x>0",
     "audience": "高中生", "difficulty": "core", "source": "精选"},
]


def _generate() -> None:
    from knowling.capabilities.qa import QAConfig
    from knowling.engine import Config, generate_knowling
    from knowling.providers.zhipu import ZhipuProvider
    from knowling.schema import KnowledgePoint

    os.makedirs(COMPONENTS, exist_ok=True)
    os.makedirs(SPECS, exist_ok=True)
    source = "GLM-5" if ZhipuProvider.available() else "离线模板"
    cfg = Config(quiet=True, qa=QAConfig(sandbox_name="auto"))
    manifest = []
    for ex in EXAMPLES:
        kp = KnowledgePoint(
            id=ex["id"], title=ex["title"], description=ex["description"],
            learning_objectives=[o.strip() for o in ex["objectives"].split(",") if o.strip()],
            difficulty=ex["difficulty"], audience=ex["audience"])
        print(f"[gen] {ex['title']} …")
        k = generate_knowling(kp, cfg, out_path=os.path.join(COMPONENTS, ex["id"] + ".html"))
        with open(os.path.join(SPECS, ex["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(k.spec.to_dict(), f, ensure_ascii=False, indent=2)
        manifest.append({
            "title": ex["title"], "file": ex["id"] + ".html",
            "source": ex.get("source", source),
            "kp": ex["description"], "audience": ex["audience"],
            "blocks": [b.type for b in k.spec.blocks],
            "qa": {"render": k.qa.score_render, "interact": k.qa.score_interact,
                   "peda": k.qa.score_peda, "learn": k.qa.score_learn, "passed": k.qa.passed},
            "status": k.status, "featured": ex.get("featured", False),
        })
        print(f"      status={k.status} qa={manifest[-1]['qa']}")
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[gen] wrote {len(manifest)} components + examples.json ({source})")


def _recompile() -> None:
    """Model-free rebuild: recompile every example from its committed blueprint
    with the current engine (prerequisites page + 4-D QA loop) and rewrite
    examples.json with fresh scores. No model needed — the specs are the source
    of truth, so this re-applies the latest engine/template to the whole deck."""
    from knowling.capabilities.qa import QAConfig
    from knowling.engine import Config, compile_spec
    from knowling.schema import KnowledgePoint, KnowlingSpec

    os.makedirs(COMPONENTS, exist_ok=True)
    cfg = Config(quiet=True, qa=QAConfig(sandbox_name="auto"))
    manifest = []
    for ex in EXAMPLES:
        sp = os.path.join(SPECS, ex["id"] + ".json")
        if not os.path.exists(sp):
            print(f"[recompile] skip {ex['id']} (no spec)")
            continue
        with open(sp, encoding="utf-8") as f:
            spec = KnowlingSpec.from_dict(json.load(f))
        kp = KnowledgePoint(id=spec.knowledge_point_id, title=ex["title"])
        print(f"[recompile] {ex['title']} …")
        k = compile_spec(spec, kp, cfg, out_path=os.path.join(COMPONENTS, ex["id"] + ".html"))
        manifest.append({
            "title": ex["title"], "file": ex["id"] + ".html",
            "source": ex.get("source", "离线模板"),
            "kp": ex["description"], "audience": ex["audience"],
            "difficulty": ex.get("difficulty", "core"),
            "blocks": [b.type for b in k.spec.blocks],
            "prereqs": len(k.spec.pedagogy.prerequisites) if k.spec.pedagogy else 0,
            "qa": {"render": k.qa.score_render, "interact": k.qa.score_interact,
                   "peda": k.qa.score_peda, "learn": k.qa.score_learn, "passed": k.qa.passed},
            "status": k.status, "featured": ex.get("featured", False),
        })
        print(f"      status={k.status} qa={manifest[-1]['qa']}")
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[recompile] wrote {len(manifest)} components + examples.json")


# ── gallery rendering ─────────────────────────────────────────────────

def _esc(s) -> str:
    return html.escape("" if s is None else str(s))


def _qa_chips(qa: dict) -> str:
    if not qa or qa.get("render") is None:
        return '<span class="score">未质检</span>'
    def s(label, v):
        cls = "ok" if (v or 0) >= 3.0 else "warn"
        return f'<span class="score {cls}">{label}<b>{v}</b></span>'
    chips = s("渲染", qa["render"]) + s("交互", qa["interact"]) + s("教学", qa["peda"])
    if qa.get("learn") is not None:
        chips += s("可学会", qa["learn"])
    return chips


_DIFF_LABEL = {"intro": "入门", "core": "核心", "advanced": "进阶"}


def _card(item: dict) -> str:
    if item["source"] == "GLM-5":
        badge = '<span class="src src-glm">GLM-5 生成</span>'
    elif item["source"] == "Math-To-Manim":
        badge = '<span class="src src-m2m">Math-To-Manim</span>'
    elif item["source"] == "精选":
        badge = '<span class="src src-pick">精选 Explorable</span>'
    else:
        badge = '<span class="src src-mock">离线模板</span>'
    status = item.get("status", "draft")
    ready = status == "ready"
    status_pill = ('<span class="pill pill-ok">ready ✓</span>' if ready
                   else f'<span class="pill pill-warn">{_esc(status)}</span>')
    diff = _DIFF_LABEL.get(item.get("difficulty", ""), item.get("difficulty", ""))
    diff_pill = f'<span class="pill">{_esc(diff)}</span>' if diff else ""
    prereqs = item.get("prereqs") or 0
    prereq_pill = f'<span class="pill pill-pre">前置 {prereqs}</span>' if prereqs else ""
    featured = " card-featured" if item.get("featured") else ""
    return f'''<article class="card{featured}">
  <div class="card-head">
    <div class="card-title"><h3>{_esc(item["title"])}</h3><p class="kp">{_esc(item["kp"])}</p></div>
    {badge}
  </div>
  <div class="meta">
    <span class="pill pill-aud">{_esc(item["audience"])}</span>
    {diff_pill}{prereq_pill}{status_pill}
  </div>
  <div class="scores">{_qa_chips(item["qa"])}</div>
  <div class="frame-wrap"><iframe loading="lazy" src="components/{_esc(item["file"])}" title="{_esc(item["title"])}"></iframe></div>
  <a class="open" href="components/{_esc(item["file"])}" target="_blank" rel="noopener">打开完整卡片 ↗</a>
</article>'''


def _render_index(manifest: list) -> str:
    manifest = sorted(manifest, key=lambda m: (not m.get("featured"),))
    cards = "\n".join(_card(i) for i in manifest)
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Knowling — 知识点学习卡片画廊</title>
<style>
:root {{ --ink:#161b26; --muted:#5c6675; --accent:#4f46e5; --accent2:#0ea5e9;
  --surface:#ffffff; --border:#e6e9f2; --soft:#f3f5fb; --ok:#0f9d58; --warn:#d9930a;
  --radius:18px; --grad:linear-gradient(135deg,#4f46e5,#0ea5e9);
  --shadow:0 1px 2px rgba(16,24,40,.04), 0 10px 30px rgba(16,24,40,.06);
  --shadow-lg:0 22px 54px rgba(79,70,229,.18); }}
* {{ box-sizing:border-box; }}
body {{ margin:0; color:var(--ink); min-height:100vh; background-attachment:fixed;
  background:
    radial-gradient(1200px 620px at 50% -320px, #e7eaff 0%, rgba(231,234,255,0) 60%),
    linear-gradient(180deg, #fafbff 0%, #eef1f8 100%);
  font:16px/1.65 -apple-system,"Segoe UI","PingFang SC","Hiragino Sans GB",sans-serif;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility; }}
a {{ color:var(--accent); text-decoration:none; }}
.wrap {{ max-width:1200px; margin:0 auto; padding:0 22px; }}
header.hero {{ padding:84px 0 36px; text-align:center; }}
.hero h1 {{ font-size:60px; margin:0 0 8px; font-weight:820; letter-spacing:-.03em; }}
.hero h1 .ling {{ background:var(--grad); -webkit-background-clip:text; background-clip:text; color:transparent; }}
.hero .tag {{ font-size:19px; color:var(--muted); max-width:660px; margin:0 auto 28px; }}
.hero .tag b {{ color:var(--ink); }}
.pipeline {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:center; align-items:center; font-size:13.5px; }}
.pipeline .step {{ background:var(--surface); border:1px solid var(--border); padding:7px 15px; border-radius:999px; box-shadow:var(--shadow); }}
.pipeline .step.qa {{ border-color:transparent; background:var(--grad); color:#fff; }}
.pipeline .arrow {{ color:#aeb6c6; }}
.ghbtn {{ margin:24px 0 34px; }}
.ghbtn a {{ display:inline-flex; align-items:center; gap:8px; padding:9px 18px; border-radius:999px;
  background:var(--ink); color:#fff; font-size:14px; font-weight:620; box-shadow:var(--shadow);
  transition:transform .14s ease, box-shadow .2s ease; }}
.ghbtn a:hover {{ transform:translateY(-2px); box-shadow:var(--shadow-lg); }}
.ghbtn svg {{ display:block; }}
.scope {{ margin:26px auto 0; max-width:780px; font-size:13.5px; color:var(--muted); }}
.scope b {{ color:var(--ink); }}
.gallery {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(450px,1fr)); gap:26px; padding:42px 0 96px; align-items:start; }}
.card {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  overflow:hidden; display:flex; flex-direction:column; box-shadow:var(--shadow);
  transition:transform .16s ease, box-shadow .2s ease; }}
.card:hover {{ transform:translateY(-3px); box-shadow:var(--shadow-lg); }}
.card-featured {{ grid-column:1/-1; border-color:rgba(79,70,229,.4); }}
.card-featured .frame-wrap {{ min-height:600px; }}
.card-head {{ display:flex; justify-content:space-between; gap:14px; align-items:flex-start; padding:20px 22px 0; }}
.card-title h3 {{ margin:0 0 5px; font-size:20px; font-weight:740; letter-spacing:-.01em; }}
.kp {{ margin:0; color:var(--muted); font-size:14px; line-height:1.5; }}
.src {{ font-size:11.5px; padding:5px 11px; border-radius:999px; white-space:nowrap; font-weight:650; align-self:flex-start; }}
.src-glm {{ background:rgba(79,70,229,.1); color:var(--accent); border:1px solid rgba(79,70,229,.28); }}
.src-mock {{ background:var(--soft); color:var(--muted); border:1px solid var(--border); }}
.src-m2m {{ background:rgba(249,115,22,.12); color:#c2620e; border:1px solid rgba(249,115,22,.3); }}
.src-pick {{ background:rgba(15,157,88,.12); color:var(--ok); border:1px solid rgba(15,157,88,.32); }}
.meta {{ display:flex; flex-wrap:wrap; gap:7px; padding:14px 22px 0; align-items:center; }}
.pill {{ font-size:12px; padding:4px 11px; border-radius:999px; background:var(--soft); color:var(--muted); border:1px solid var(--border); }}
.pill-aud {{ color:var(--ink); }}
.pill-pre {{ color:var(--accent); border-color:rgba(79,70,229,.28); background:rgba(79,70,229,.07); }}
.pill-ok {{ color:var(--ok); border-color:rgba(15,157,88,.32); background:rgba(15,157,88,.08); font-weight:600; }}
.pill-warn {{ color:var(--warn); border-color:rgba(217,147,10,.34); background:rgba(217,147,10,.08); }}
.scores {{ display:flex; flex-wrap:wrap; gap:6px; padding:12px 22px 2px; }}
.score {{ font-size:11.5px; padding:4px 9px; border-radius:9px; font-variant-numeric:tabular-nums;
  background:var(--soft); color:var(--muted); border:1px solid var(--border); }}
.score b {{ margin-left:5px; font-weight:780; }}
.score.ok {{ color:var(--ok); border-color:rgba(15,157,88,.28); background:rgba(15,157,88,.07); }}
.score.warn {{ color:var(--warn); border-color:rgba(217,147,10,.3); }}
.frame-wrap {{ height:auto; min-height:520px; margin:16px 0 0; background:#fff; border-top:1px solid var(--border); }}
iframe {{ width:100%; min-height:520px; border:0; display:block; }}
.open {{ padding:13px 22px; font-size:13.5px; border-top:1px solid var(--border); color:var(--accent); font-weight:600; }}
.open:hover {{ background:var(--soft); }}
footer {{ border-top:1px solid var(--border); padding:30px 0 72px; color:var(--muted); font-size:13px; text-align:center; }}
code {{ background:var(--soft); padding:1px 6px; border-radius:5px; font-size:.9em; }}
@media (max-width:560px) {{ .hero h1 {{ font-size:44px; }} .gallery {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header class="hero"><div class="wrap">
  <h1>Know<span class="ling">ling</span></h1>
  <p class="tag">输入一个细小的 <b>知识点</b>，输出一张自包含、可交互、经过质检的 <b>学习卡片</b>。每张卡先讲清前置知识，再逐张推进学习。</p>
  <p class="ghbtn"><a href="https://github.com/fxp/Knowling" target="_blank" rel="noopener"><svg viewBox="0 0 16 16" width="17" height="17" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg>在 GitHub 查看源码 · fxp/Knowling ↗</a></p>
  <div class="pipeline">
    <span class="step">知识点</span><span class="arrow">→</span>
    <span class="step">蓝图 Spec</span><span class="arrow">→</span>
    <span class="step">前置知识页</span><span class="arrow">→</span>
    <span class="step">模板编译</span><span class="arrow">→</span>
    <span class="step qa">四维质检</span><span class="arrow">→</span>
    <span class="step">卡片牌组</span>
  </div>
  <p class="scope">下方 <b>{len(manifest)}</b> 张卡片均可直接交互，每张都以「前置知识」开场。四维质检 = 渲染 + 交互 + 教学（含是否跑题）+ <b>可学会</b>（模拟已掌握前置知识的学习者，只读卡片能否学会该知识点）。</p>
</div></header>
<main class="wrap"><section class="gallery">
{cards}
</section></main>
<footer><div class="wrap">
  由 Knowling 生成 · 每张卡片均为单文件自包含 HTML（内联 CSS/JS，无外部依赖）· 用 <code>python3 demo/build.py --recompile</code> 可免模型从蓝图重建全部卡片 · <code>knowling serve</code> 可对卡片对话式改写 · 源码托管于 <a href="https://github.com/fxp/Knowling" target="_blank" rel="noopener">GitHub · fxp/Knowling ↗</a>。
</div></footer>
<script>
/* Size each embedded card to its content so nothing is clipped. The gallery and
   the components share an origin (GitHub Pages), so we can read the iframe's
   document height. The card deck animates its own height on navigation; a
   ResizeObserver inside the frame keeps the iframe matched. */
(function () {{
  function fit(f) {{
    try {{
      var d = f.contentDocument; if (!d) return;
      var doc = d.querySelector('.kl-doc') || d.body; if (!doc) return;
      var h = Math.ceil(doc.getBoundingClientRect().height) + 6;
      if (h > 60) f.style.height = h + 'px';
    }} catch (e) {{ /* cross-origin or not ready — keep CSS min-height */ }}
  }}
  function bind(f) {{
    function refit() {{ fit(f); }}
    // Attach live height tracking once the frame's document is ready. Called from
    // both the load event and the already-loaded fallback so navigation resizes
    // work either way.
    function wire() {{
      refit();
      try {{
        var w = f.contentWindow, d = f.contentDocument;
        var target = d.querySelector('.kl-doc');
        if (w.ResizeObserver && target) {{
          new w.ResizeObserver(refit).observe(target);  // tracks the deck's animated height
        }} else {{
          // no ResizeObserver: re-fit after the deck's height animation on nav
          d.addEventListener('click', function () {{ setTimeout(refit, 120); setTimeout(refit, 460); }});
          w.addEventListener('keydown', function () {{ setTimeout(refit, 460); }});
        }}
      }} catch (e) {{}}
      setTimeout(refit, 300); setTimeout(refit, 850);
    }}
    f.addEventListener('load', wire);
    // already loaded before this script ran (cache / bfcache restore)
    try {{ if (f.contentDocument && f.contentDocument.readyState === 'complete') wire(); }} catch (e) {{}}
  }}
  document.querySelectorAll('.frame-wrap iframe').forEach(bind);
  window.addEventListener('resize', function () {{
    document.querySelectorAll('.frame-wrap iframe').forEach(fit);
  }});
}})();
</script>
</body>
</html>'''


def _rerender() -> None:
    """Re-render components from saved specs (no model) — applies template/CSS
    changes (e.g. math rendering) to existing examples for free."""
    from knowling.assembler import assemble_html
    from knowling.schema import KnowlingSpec

    if not os.path.isdir(SPECS):
        print("no demo/specs — run --generate first")
        return
    for ex in EXAMPLES:
        sp = os.path.join(SPECS, ex["id"] + ".json")
        if not os.path.exists(sp):
            print(f"[rerender] skip {ex['id']} (no saved spec)")
            continue
        from knowling import blocks
        spec = KnowlingSpec.from_dict(json.load(open(sp, encoding="utf-8")))
        frags = [blocks.render_block_template(b.to_dict()) for b in spec.blocks]
        html = assemble_html(spec, frags, ex["title"])
        with open(os.path.join(COMPONENTS, ex["id"] + ".html"), "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[rerender] {ex['id']}")


def main() -> None:
    if "--generate" in sys.argv:
        _generate()
    elif "--recompile" in sys.argv:
        _recompile()
    elif "--rerender" in sys.argv:
        _rerender()
    if not os.path.exists(MANIFEST):
        print("no examples.json — run: python3 demo/build.py --generate")
        return
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(_render_index(manifest))
    print(f"wrote demo/index.html with {len(manifest)} components")


if __name__ == "__main__":
    main()
