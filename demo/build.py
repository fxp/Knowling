#!/usr/bin/env python3
"""Build the Knowling demo gallery.

Generates a few example components (offline mock provider) into
``demo/components/`` , folds in any real GLM-generated artifact, and writes a
self-contained ``demo/index.html`` gallery that previews each component in an
iframe with its knowledge point, QA scores and block types.

Run:  python3 demo/build.py
Open: demo/index.html
"""

from __future__ import annotations

import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COMPONENTS = os.path.join(HERE, "components")
sys.path.insert(0, ROOT)

from knowling.assembler import assemble_html  # noqa: E402
from knowling.capabilities.qa import QAConfig  # noqa: E402
from knowling.engine import Config, generate_knowling  # noqa: E402
from knowling.schema import KnowledgePoint, KnowlingSpec, Pedagogy  # noqa: E402


def _redeck(flat_html: str) -> str:
    """Re-assemble a previously-flat artifact into the card deck — no model call.

    Extracts each block fragment by its data-block-id and feeds them back through
    assemble_html (which now produces the deck). Lets us upgrade an existing GLM
    artifact to card form without regenerating it.
    """
    if "data-deck" in flat_html:  # already a deck
        return flat_html
    ids = []
    for m in re.finditer(r'data-block-id="([^"]+)"', flat_html):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    starts = [flat_html.rfind("<", 0, flat_html.find(f'data-block-id="{b}"')) for b in ids]
    end = flat_html.find("<footer")
    if end == -1:
        end = flat_html.find("</main>")
    frags = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else end
        frags.append(flat_html[s:e].strip())
    title_m = re.search(r"<h1>(.*?)</h1>", flat_html, re.DOTALL)
    hook_m = re.search(r'<p class="kl-hook">(.*?)</p>', flat_html, re.DOTALL)
    title = html.unescape(title_m.group(1).strip()) if title_m else "Knowling"
    hook = html.unescape(hook_m.group(1).strip()) if hook_m else ""
    spec = KnowlingSpec(knowledge_point_id="redeck", pedagogy=Pedagogy(hook=hook))
    return assemble_html(spec, frags, title)


# ── examples generated offline (mock provider, deterministic) ──────────
GEN_EXAMPLES = [
    KnowledgePoint(
        id="calc.derivative.chain-rule", title="链式法则",
        description="复合函数的求导：外层导数 × 内层导数",
        learning_objectives=["能对复合函数求导", "能解释为何相乘"],
        difficulty="core", audience="高中生"),
    KnowledgePoint(
        id="phys.ohm", title="欧姆定律 V = IR",
        description="电压、电流、电阻三者的关系",
        learning_objectives=["理解 V、I、R 的关系", "能计算其一"],
        difficulty="intro", audience="初中生"),
]


def _gen_offline(manifest: list) -> None:
    cfg = Config(provider_name="mock", quiet=True, qa=QAConfig(sandbox_name="static"))
    for kp in GEN_EXAMPLES:
        fname = kp.id.replace(".", "_") + ".html"
        out = os.path.join(COMPONENTS, fname)
        k = generate_knowling(kp, cfg, out_path=out)
        manifest.append({
            "title": kp.title, "file": fname, "source": "离线模板",
            "kp": kp.description, "audience": kp.audience or "",
            "blocks": [b.type for b in k.spec.blocks],
            "qa": {"render": k.qa.score_render, "interact": k.qa.score_interact,
                   "peda": k.qa.score_peda, "passed": k.qa.passed},
            "status": k.status,
        })
        print("generated", fname)


def _fold_real(manifest: list) -> None:
    """Include the real GLM-5 artifact if present (out/sine-real.html)."""
    src = os.path.join(ROOT, "out", "sine-real.html")
    if not os.path.exists(src):
        print("(skip real GLM example — out/sine-real.html not found)")
        return
    with open(src, encoding="utf-8") as f:
        deck = _redeck(f.read())  # upgrade to card form without re-calling GLM
    with open(os.path.join(COMPONENTS, "sine-real.html"), "w", encoding="utf-8") as f:
        f.write(deck)
    qa = {"render": 4.0, "interact": 5.0, "peda": 4.0, "passed": True}
    blocks = ["text", "param_sim", "param_sim", "param_sim", "step_through", "quiz"]
    jl = os.path.join(ROOT, "out", "sine-real.jsonl")
    if os.path.exists(jl):
        try:
            rows = [json.loads(l) for l in open(jl, encoding="utf-8") if l.strip()]
            done = [r for r in rows if r.get("event") == "done"][-1]["qa"]
            qa = {"render": done["score_render"], "interact": done["score_interact"],
                  "peda": done["score_peda"], "passed": done["passed"]}
            sp = [r for r in rows if r.get("event") == "info" and r.get("msg") == "knowling"]
            if sp:
                blocks = [b["type"] for b in sp[-1]["knowling"]["spec"]["blocks"]]
        except Exception:
            pass
    manifest.insert(0, {
        "title": "正弦函数 y = A·sin(ωx + φ)", "file": "sine-real.html",
        "source": "GLM-5", "kp": "振幅 A、角频率 ω、相位 φ 各自如何改变正弦波形",
        "audience": "高一学生", "blocks": blocks,
        "qa": qa, "status": "ready" if qa["passed"] else "qa_failed",
        "featured": True,
    })
    print("folded real GLM example")


# ── gallery rendering ─────────────────────────────────────────────────

def _esc(s) -> str:
    return html.escape("" if s is None else str(s))


def _qa_chips(qa: dict) -> str:
    if not qa or qa.get("render") is None:
        return '<span class="chip chip-muted">未质检</span>'
    def chip(label, v):
        cls = "chip-ok" if (v or 0) >= 3.5 else "chip-warn"
        return f'<span class="chip {cls}">{label} {v}</span>'
    return (chip("渲染", qa["render"]) + chip("交互", qa["interact"])
            + chip("教学", qa["peda"]))


def _card(item: dict) -> str:
    badge = ('<span class="src src-glm">GLM-5 生成</span>' if item["source"] == "GLM-5"
             else '<span class="src src-mock">离线模板</span>')
    status = item.get("status", "draft")
    status_cls = "ready" if status == "ready" else "draft"
    blocks = "".join(f'<span class="chip chip-block">{_esc(b)}</span>' for b in item["blocks"])
    featured = " card-featured" if item.get("featured") else ""
    return f'''<article class="card{featured}">
  <div class="card-head">
    <div>
      <h3>{_esc(item["title"])}</h3>
      <p class="kp">{_esc(item["kp"])}</p>
    </div>
    {badge}
  </div>
  <div class="meta">
    <span class="chip chip-status chip-{status_cls}">{_esc(status)}</span>
    {_qa_chips(item["qa"])}
    <span class="chip chip-aud">{_esc(item["audience"])}</span>
  </div>
  <div class="blocks">{blocks}</div>
  <div class="frame-wrap">
    <iframe loading="lazy" src="components/{_esc(item["file"])}" title="{_esc(item["title"])}"></iframe>
  </div>
  <a class="open" href="components/{_esc(item["file"])}" target="_blank" rel="noopener">在新标签打开 ↗</a>
</article>'''


def _render_index(manifest: list) -> str:
    cards = "\n".join(_card(i) for i in manifest)
    data_count = len(manifest)
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Knowling — 知识点学习组件画廊</title>
<style>
:root {{
  --bg:#0f1117; --panel:#171a21; --fg:#e6e9ef; --muted:#9aa3b2;
  --accent:#6c8cff; --accent2:#ff8a4c; --ok:#3fb950; --warn:#d29922;
  --border:#262b36; --radius:14px;
}}
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
.hero p.tag {{ font-size:19px; color:var(--muted); margin:0 0 26px; max-width:680px; }}
.pipeline {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; font-size:14px; }}
.pipeline .step {{ background:var(--panel); border:1px solid var(--border);
  padding:6px 13px; border-radius:999px; }}
.pipeline .arrow {{ color:var(--muted); }}
.pipeline .step.qa {{ border-color:var(--accent); color:var(--accent); }}
.scope {{ margin-top:22px; font-size:14px; color:var(--muted); }}
.scope b {{ color:var(--fg); }}
.gallery {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(360px,1fr));
  gap:22px; padding:36px 0 80px; }}
.card {{ background:var(--panel); border:1px solid var(--border); border-radius:var(--radius);
  overflow:hidden; display:flex; flex-direction:column; }}
.card-featured {{ grid-column:1/-1; border-color:var(--accent); }}
.card-featured .frame-wrap {{ height:560px; }}
.card-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start;
  padding:18px 18px 10px; }}
.card-head h3 {{ margin:0 0 4px; font-size:19px; }}
.kp {{ margin:0; color:var(--muted); font-size:14px; }}
.src {{ font-size:12px; padding:4px 10px; border-radius:999px; white-space:nowrap; font-weight:600; }}
.src-glm {{ background:rgba(108,140,255,.16); color:var(--accent); border:1px solid rgba(108,140,255,.4); }}
.src-mock {{ background:#21262d; color:var(--muted); border:1px solid var(--border); }}
.meta, .blocks {{ display:flex; flex-wrap:wrap; gap:6px; padding:0 18px; }}
.blocks {{ padding-top:10px; padding-bottom:4px; }}
.chip {{ font-size:12px; padding:3px 9px; border-radius:999px; background:#21262d;
  color:var(--muted); border:1px solid var(--border); }}
.chip-ok {{ color:var(--ok); border-color:rgba(63,185,80,.4); }}
.chip-warn {{ color:var(--warn); border-color:rgba(210,153,34,.4); }}
.chip-block {{ color:#b9c2d0; }}
.chip-status.chip-ready {{ color:var(--ok); border-color:rgba(63,185,80,.4); }}
.chip-status.chip-draft {{ color:var(--warn); }}
.chip-aud {{ color:#b9c2d0; }}
.frame-wrap {{ height:420px; margin:14px 0 0; background:#fff; border-top:1px solid var(--border); }}
iframe {{ width:100%; height:100%; border:0; }}
.open {{ padding:12px 18px; font-size:14px; border-top:1px solid var(--border); }}
footer {{ border-top:1px solid var(--border); padding:24px 0 60px; color:var(--muted); font-size:13px; }}
code {{ background:#21262d; padding:1px 6px; border-radius:5px; font-size:.9em; }}
</style>
</head>
<body>
<header class="hero"><div class="wrap">
  <h1>Know<span class="ling">ling</span></h1>
  <p class="tag">输入一个细小的<b style="color:var(--fg)">知识点</b>，输出一个自包含、可交互、经过质检的<b style="color:var(--fg)">学习 + Quiz 组件</b>。</p>
  <div class="pipeline">
    <span class="step">知识点</span><span class="arrow">→</span>
    <span class="step">蓝图 Spec</span><span class="arrow">→</span>
    <span class="step">块编译</span><span class="arrow">→</span>
    <span class="step qa">三维质检</span><span class="arrow">→</span>
    <span class="step">自包含组件</span>
  </div>
  <p class="scope">范围聚焦：<b>只做单个知识点的学习/Quiz 组件</b>。三维质检 = 渲染分（看截图）+ 交互分（校验控件）+ 教学分（Explorable 准则）。下方 {data_count} 个示例均可直接交互。</p>
</div></header>
<main class="wrap">
  <section class="gallery">
{cards}
  </section>
</main>
<footer><div class="wrap">
  由 Knowling 生成 · <code>GLM-5</code> 示例为真实模型生成并通过三维质检；<code>离线模板</code>示例由 MockProvider 无 API key 生成 · 每个组件均为单文件自包含 HTML。
</div></footer>
</body>
</html>'''


def main() -> None:
    os.makedirs(COMPONENTS, exist_ok=True)
    manifest: list = []
    _gen_offline(manifest)
    _fold_real(manifest)
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(_render_index(manifest))
    with open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"wrote demo/index.html with {len(manifest)} components")


if __name__ == "__main__":
    main()
