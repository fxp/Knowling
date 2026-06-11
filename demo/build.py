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
     "audience": "高一学生", "difficulty": "core", "featured": True},
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


# ── gallery rendering ─────────────────────────────────────────────────

def _esc(s) -> str:
    return html.escape("" if s is None else str(s))


def _qa_chips(qa: dict) -> str:
    if not qa or qa.get("render") is None:
        return '<span class="chip chip-muted">未质检</span>'
    def chip(label, v):
        cls = "chip-ok" if (v or 0) >= 3.0 else "chip-warn"
        return f'<span class="chip {cls}">{label} {v}</span>'
    chips = chip("渲染", qa["render"]) + chip("交互", qa["interact"]) + chip("教学", qa["peda"])
    if qa.get("learn") is not None:
        chips += chip("可学会", qa["learn"])
    return chips


def _card(item: dict) -> str:
    if item["source"] == "GLM-5":
        badge = '<span class="src src-glm">GLM-5 生成</span>'
    elif item["source"] == "Math-To-Manim":
        badge = '<span class="src src-m2m">Math-To-Manim</span>'
    else:
        badge = '<span class="src src-mock">离线模板</span>'
    status = item.get("status", "draft")
    status_cls = "ready" if status == "ready" else "draft"
    blocks = "".join(f'<span class="chip chip-block">{_esc(b)}</span>' for b in item["blocks"])
    featured = " card-featured" if item.get("featured") else ""
    return f'''<article class="card{featured}">
  <div class="card-head">
    <div><h3>{_esc(item["title"])}</h3><p class="kp">{_esc(item["kp"])}</p></div>
    {badge}
  </div>
  <div class="meta">
    <span class="chip chip-status chip-{status_cls}">{_esc(status)}</span>
    {_qa_chips(item["qa"])}
    <span class="chip chip-aud">{_esc(item["audience"])}</span>
  </div>
  <div class="blocks">{blocks}</div>
  <div class="frame-wrap"><iframe loading="lazy" src="components/{_esc(item["file"])}" title="{_esc(item["title"])}"></iframe></div>
  <a class="open" href="components/{_esc(item["file"])}" target="_blank" rel="noopener">在新标签打开 ↗</a>
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
:root {{ --bg:#0f1117; --panel:#171a21; --fg:#e6e9ef; --muted:#9aa3b2; --accent:#6c8cff;
  --accent2:#ff8a4c; --border:#262b36; --ok:#3fb950; --warn:#d29922; --radius:14px; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg);
  font:16px/1.6 -apple-system,"Segoe UI","PingFang SC","Hiragino Sans GB",sans-serif; }}
a {{ color:var(--accent); text-decoration:none; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:0 20px; }}
header.hero {{ padding:64px 0 36px; border-bottom:1px solid var(--border);
  background:radial-gradient(1200px 400px at 50% -120px, rgba(108,140,255,.18), transparent); }}
.hero h1 {{ font-size:44px; margin:0 0 10px; letter-spacing:-.5px; }}
.hero h1 .ling {{ background:linear-gradient(90deg,var(--accent),var(--accent2));
  -webkit-background-clip:text; background-clip:text; color:transparent; }}
.hero p.tag {{ font-size:19px; color:var(--muted); margin:0 0 26px; max-width:720px; }}
.pipeline {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; font-size:14px; }}
.pipeline .step {{ background:var(--panel); border:1px solid var(--border); padding:6px 13px; border-radius:999px; }}
.pipeline .arrow {{ color:var(--muted); }}
.pipeline .step.qa {{ border-color:var(--accent); color:var(--accent); }}
.scope {{ margin-top:22px; font-size:14px; color:var(--muted); }}
.scope b {{ color:var(--fg); }}
.gallery {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(440px,1fr)); gap:22px; padding:36px 0 80px; align-items:start; }}
.card {{ background:var(--panel); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; display:flex; flex-direction:column; }}
.card-featured {{ grid-column:1/-1; border-color:var(--accent); }}
.card-featured .frame-wrap {{ min-height:600px; }}
.card-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; padding:18px 18px 10px; }}
.card-head h3 {{ margin:0 0 4px; font-size:19px; }}
.kp {{ margin:0; color:var(--muted); font-size:14px; }}
.src {{ font-size:12px; padding:4px 10px; border-radius:999px; white-space:nowrap; font-weight:600; }}
.src-glm {{ background:rgba(108,140,255,.16); color:var(--accent); border:1px solid rgba(108,140,255,.4); }}
.src-mock {{ background:#21262d; color:var(--muted); border:1px solid var(--border); }}
.src-m2m {{ background:rgba(255,138,76,.16); color:var(--accent2); border:1px solid rgba(255,138,76,.4); }}
.meta, .blocks {{ display:flex; flex-wrap:wrap; gap:6px; padding:0 18px; }}
.blocks {{ padding-top:10px; padding-bottom:4px; }}
.chip {{ font-size:12px; padding:3px 9px; border-radius:999px; background:#21262d; color:var(--muted); border:1px solid var(--border); }}
.chip-ok {{ color:var(--ok); border-color:rgba(63,185,80,.4); }}
.chip-warn {{ color:var(--warn); border-color:rgba(210,153,34,.4); }}
.chip-block {{ color:#b9c2d0; }}
.chip-status.chip-ready {{ color:var(--ok); border-color:rgba(63,185,80,.4); }}
.chip-status.chip-draft {{ color:var(--warn); }}
.chip-aud {{ color:#b9c2d0; }}
.frame-wrap {{ height:auto; min-height:520px; margin:14px 0 0; background:#fff; border-top:1px solid var(--border); }}
iframe {{ width:100%; min-height:520px; border:0; display:block; }}
.open {{ padding:12px 18px; font-size:14px; border-top:1px solid var(--border); }}
footer {{ border-top:1px solid var(--border); padding:24px 0 60px; color:var(--muted); font-size:13px; }}
code {{ background:#21262d; padding:1px 6px; border-radius:5px; font-size:.9em; }}
</style>
</head>
<body>
<header class="hero"><div class="wrap">
  <h1>Know<span class="ling">ling</span></h1>
  <p class="tag">输入一个细小的<b style="color:var(--fg)">知识点</b>，输出一张自包含、可交互、经过质检的<b style="color:var(--fg)">学习卡片</b>。每张卡片一次只讲一个部分，逐张推进。</p>
  <div class="pipeline">
    <span class="step">知识点</span><span class="arrow">→</span>
    <span class="step">蓝图 Spec</span><span class="arrow">→</span>
    <span class="step">模板编译</span><span class="arrow">→</span>
    <span class="step qa">四维质检</span><span class="arrow">→</span>
    <span class="step">知识卡片牌组</span>
  </div>
  <p class="scope">范围聚焦：<b>只做单个知识点的学习 / Quiz 卡片</b>。四维质检 = 渲染分（GLM-5V 看截图）+ 交互分（校验控件）+ 教学分（含「是否跑题」）+ 可学会分（模拟已掌握前置知识的学习者，只读卡片能否获得该知识点所需知识）。下方 {len(manifest)} 个示例均可直接交互。</p>
</div></header>
<main class="wrap"><section class="gallery">
{cards}
</section></main>
<footer><div class="wrap">
  由 Knowling 生成 · <code>GLM-5</code> 示例为真实模型规划内容、统一模板渲染并通过四维质检 · 每张卡片均为单文件自包含 HTML · 用 <code>knowling serve</code> 可对卡片对话式改写。
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
    f.addEventListener('load', function () {{
      refit();
      try {{
        var w = f.contentWindow, d = f.contentDocument;
        var target = d.querySelector('.kl-doc');
        if (w.ResizeObserver && target) {{ new w.ResizeObserver(refit).observe(target); }}
        d.addEventListener('click', function () {{ setTimeout(refit, 120); setTimeout(refit, 460); }});
        w.addEventListener('keydown', function () {{ setTimeout(refit, 460); }});
      }} catch (e) {{}}
      setTimeout(refit, 300); setTimeout(refit, 850);
    }});
    if (f.contentDocument && f.contentDocument.readyState === 'complete') refit();
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
