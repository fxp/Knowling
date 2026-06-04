"""Assemble compiled block fragments into one self-contained artifact (design §5 ④).

P0 supports the ``html`` target: a single .html file with inline CSS/JS and no
external runtime deps (design §3.1 #5). The ``.kl-*`` design tokens give all
blocks a consistent look; LLM-generated blocks are told to reuse them.
"""

from __future__ import annotations

import html as _html
from typing import List

from .schema import KnowlingSpec

_CSS = """
:root {
  --kl-bg: #ffffff; --kl-fg: #1f2328; --kl-muted: #57606a;
  --kl-accent: #3056d3; --kl-accent-2: #e8590c;
  --kl-border: #d0d7de; --kl-soft: #f6f8fa; --kl-radius: 10px;
  --kl-ok: #1a7f37; --kl-bad: #cf222e;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--kl-soft); color: var(--kl-fg);
  font: 16px/1.65 -apple-system, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
}
.kl-doc { max-width: 760px; margin: 0 auto; padding: 32px 20px 80px; }
.kl-header { margin-bottom: 24px; }
.kl-header h1 { font-size: 28px; margin: 0 0 6px; }
.kl-hook { color: var(--kl-muted); font-size: 15px; margin: 0; }
.kl-block {
  background: var(--kl-bg); border: 1px solid var(--kl-border);
  border-radius: var(--kl-radius); padding: 20px 22px; margin: 18px 0;
}
.kl-block h2, .kl-block h3 { margin-top: 0; }
.kl-block code { background: var(--kl-soft); padding: 1px 5px; border-radius: 5px; font-size: .9em; }
/* quiz */
.kl-quiz-q { font-weight: 600; }
.kl-quiz-opts { display: flex; flex-direction: column; gap: 8px; margin: 12px 0; }
.kl-quiz-opt {
  text-align: left; padding: 10px 14px; border: 1px solid var(--kl-border);
  border-radius: 8px; background: var(--kl-bg); cursor: pointer; font: inherit;
  transition: background .15s, border-color .15s;
}
.kl-quiz-opt:hover { background: var(--kl-soft); }
.kl-quiz-opt.is-correct { border-color: var(--kl-ok); background: #e6f6ea; }
.kl-quiz-opt.is-wrong { border-color: var(--kl-bad); background: #fde8e8; }
.kl-quiz-opt.is-selected { border-color: var(--kl-accent); background: #eef1fb; }
.kl-quiz-feedback { margin: 4px 0 0; font-size: 14px; }
.kl-quiz-feedback.is-correct { color: var(--kl-ok); }
.kl-quiz-feedback.is-wrong { color: var(--kl-bad); }
.kl-quiz-title { font-weight: 600; margin: 0 0 4px; }
.kl-quiz-progress { color: var(--kl-muted); font-size: 13px; font-variant-numeric: tabular-nums; }
.kl-quiz-input { width: 100%; padding: 10px 12px; border: 1px solid var(--kl-border); border-radius: 8px; font: inherit; }
.kl-quiz-actions { display: flex; gap: 10px; margin-top: 12px; }
.kl-quiz-submit, .kl-quiz-next, .kl-quiz-redo {
  font: inherit; padding: 7px 18px; border: 1px solid var(--kl-accent);
  border-radius: 8px; background: var(--kl-accent); color: #fff; cursor: pointer;
}
.kl-quiz-next { background: var(--kl-bg); color: var(--kl-accent); }
.kl-quiz-submit:disabled { opacity: .5; cursor: default; }
.kl-quiz-score { margin-top: 14px; font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 12px; }
.kl-quiz-redo { background: var(--kl-bg); color: var(--kl-accent); font-weight: 400; }
/* param_sim */
.kl-ps-controls { display: flex; flex-direction: column; gap: 12px; }
.kl-ps-ctl { display: grid; grid-template-columns: 120px 1fr 64px; align-items: center; gap: 12px; }
.kl-ps-name { font-size: 14px; color: var(--kl-muted); }
.kl-ps-ctl input[type=range] { width: 100%; accent-color: var(--kl-accent); }
.kl-ps-val { font-variant-numeric: tabular-nums; text-align: right; font-weight: 600; }
.kl-ps-outputs { display: flex; flex-wrap: wrap; gap: 16px; margin: 16px 0; }
.kl-ps-out { background: var(--kl-soft); border-radius: 8px; padding: 8px 14px; }
.kl-ps-out span { color: var(--kl-muted); font-size: 13px; margin-right: 8px; }
.kl-ps-out strong { font-variant-numeric: tabular-nums; color: var(--kl-accent); }
.kl-ps-canvas { width: 100%; height: auto; background: var(--kl-bg); border: 1px solid var(--kl-border); border-radius: 8px; }
.kl-ps-explain { color: var(--kl-muted); font-size: 14px; }
/* callout */
.kl-callout { display: flex; gap: 12px; align-items: flex-start; border-left: 4px solid var(--kl-accent); }
.kl-callout-icon { font-size: 18px; line-height: 1.6; }
.kl-callout-body > :first-child { margin-top: 0; }
.kl-callout-tip { border-left-color: var(--kl-ok); }
.kl-callout-warning { border-left-color: #bf8700; }
.kl-callout-danger { border-left-color: var(--kl-bad); }
/* section */
.kl-section { border: none; background: transparent; padding: 8px 0; border-bottom: 2px solid var(--kl-border); border-radius: 0; }
.kl-section-title { margin: 0; }
/* figure */
.kl-figure { text-align: center; }
.kl-figure img, .kl-figure svg { max-width: 100%; height: auto; }
.kl-figure figcaption { color: var(--kl-muted); font-size: 13px; margin-top: 8px; }
/* code */
.kl-code-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.kl-code-lang { color: var(--kl-muted); font-size: 13px; }
.kl-code-copy { font: inherit; font-size: 13px; padding: 3px 10px; border: 1px solid var(--kl-border); border-radius: 6px; background: var(--kl-bg); cursor: pointer; }
.kl-code pre { background: var(--kl-soft); padding: 14px; border-radius: 8px; overflow: auto; margin: 0; }
/* flashcards */
.kl-fc-card { min-height: 96px; border: 1px solid var(--kl-border); border-radius: 10px; padding: 20px; cursor: pointer; display: grid; place-items: center; text-align: center; transition: background .15s; }
.kl-fc-card:hover { background: var(--kl-soft); }
.kl-fc-back { display: none; color: var(--kl-accent); }
.kl-fc-card.is-flipped .kl-fc-front { display: none; }
.kl-fc-card.is-flipped .kl-fc-back { display: block; }
.kl-fc-nav, .kl-st-nav, .kl-anim-nav { display: flex; align-items: center; gap: 12px; justify-content: center; margin-top: 12px; }
.kl-fc-nav button, .kl-st-nav button, .kl-anim-nav button, .kl-tl-node { font: inherit; padding: 6px 14px; border: 1px solid var(--kl-border); border-radius: 8px; background: var(--kl-bg); cursor: pointer; }
.kl-fc-count, .kl-st-progress, .kl-anim-frame { color: var(--kl-muted); font-variant-numeric: tabular-nums; }
button:disabled { opacity: .45; cursor: default; }
/* step_through */
.kl-st-state { background: var(--kl-soft); border-radius: 8px; padding: 16px; font-family: ui-monospace, monospace; white-space: pre-wrap; }
.kl-st-explain { color: var(--kl-muted); }
/* timeline */
.kl-tl-track { display: flex; gap: 10px; overflow-x: auto; padding-bottom: 8px; }
.kl-tl-node { display: flex; flex-direction: column; min-width: 110px; text-align: left; }
.kl-tl-node.is-active { border-color: var(--kl-accent); background: var(--kl-soft); }
.kl-tl-t { color: var(--kl-accent); font-size: 12px; }
.kl-tl-detail { margin-top: 12px; padding: 12px; background: var(--kl-soft); border-radius: 8px; }
/* interactive_demo */
.kl-id-controls { display: flex; flex-direction: column; gap: 10px; }
.kl-id-ctl { display: flex; align-items: center; gap: 12px; }
.kl-id-ctl > span { min-width: 120px; color: var(--kl-muted); font-size: 14px; }
.kl-id-outputs { display: flex; flex-wrap: wrap; gap: 16px; margin: 16px 0; }
.kl-id-out { background: var(--kl-soft); border-radius: 8px; padding: 8px 14px; }
.kl-id-out span { color: var(--kl-muted); font-size: 13px; margin-right: 8px; }
.kl-id-out strong { color: var(--kl-accent); }
.kl-id-explain { color: var(--kl-muted); font-size: 14px; }
/* animation */
.kl-anim-stage { background: var(--kl-soft); border-radius: 8px; padding: 28px; text-align: center; min-height: 60px; font-size: 18px; }
/* concept_graph */
.kl-cg-canvas { width: 100%; height: auto; background: var(--kl-bg); border: 1px solid var(--kl-border); border-radius: 8px; cursor: pointer; }
/* user_note */
.kl-usernote-area { width: 100%; border: 1px solid var(--kl-border); border-radius: 8px; padding: 10px; font: inherit; resize: vertical; }
/* deep_dive */
.kl-deepdive summary { cursor: pointer; font-weight: 600; }
/* generic fallback */
.kl-generic-tag { color: var(--kl-accent-2); font-size: 14px; }
.kl-generic pre { background: var(--kl-soft); padding: 12px; border-radius: 8px; overflow: auto; font-size: 13px; }
.kl-footer { margin-top: 32px; color: var(--kl-muted); font-size: 12px; text-align: center; }
"""


def assemble_html(spec: KnowlingSpec, fragments: List[str], title: str) -> str:
    hook = spec.pedagogy.hook if spec.pedagogy else ""
    body = "\n".join(fragments)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(title)} · Knowling</title>
<style>{_CSS}</style>
</head>
<body>
<main class="kl-doc">
  <header class="kl-header">
    <h1>{_html.escape(title)}</h1>
    {f'<p class="kl-hook">{_html.escape(hook)}</p>' if hook else ''}
  </header>
{body}
  <footer class="kl-footer">Generated by Knowling · 自包含交互学习组件</footer>
</main>
</body>
</html>"""
