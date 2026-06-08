"""Assemble compiled block fragments into one self-contained artifact (design §5 ④).

P0 supports the ``html`` target: a single .html file with inline CSS/JS and no
external runtime deps (design §3.1 #5). The ``.kl-*`` design tokens give all
blocks a consistent look; LLM-generated blocks are told to reuse them.
"""

from __future__ import annotations

import html as _html
import json as _json
from typing import List

from .schema import KnowlingSpec

_CSS = """
:root {
  --kl-bg: #ffffff; --kl-fg: #14181f; --kl-muted: #5b6573;
  --kl-accent: #4f46e5; --kl-accent-2: #0ea5e9; --kl-warm: #f97316;
  --kl-accent-soft: #eef0fe;
  --kl-border: #e7e9f0; --kl-soft: #f4f6fb; --kl-radius: 16px;
  --kl-ok: #0f9d58; --kl-ok-soft: #e7f6ec; --kl-bad: #e5484d; --kl-bad-soft: #fdebec;
  --kl-grad: linear-gradient(135deg, #4f46e5 0%, #0ea5e9 100%);
  --kl-shadow: 0 1px 2px rgba(16,24,40,.04), 0 8px 28px rgba(16,24,40,.06);
  --kl-shadow-lg: 0 12px 40px rgba(79,70,229,.14);
}
* { box-sizing: border-box; }
body {
  margin: 0; color: var(--kl-fg);
  background:
    radial-gradient(1100px 520px at 50% -240px, #e9ecff 0%, rgba(233,236,255,0) 62%),
    linear-gradient(180deg, #f8fafc 0%, #eef1f8 100%);
  background-attachment: fixed; min-height: 100vh;
  font: 16px/1.7 -apple-system, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}
.kl-doc { max-width: 800px; margin: 0 auto; padding: 44px 20px 96px; }
.kl-header { margin-bottom: 28px; text-align: center; }
.kl-header h1 {
  font-size: 31px; line-height: 1.25; margin: 0 0 10px; font-weight: 760;
  letter-spacing: -.022em;
  background: linear-gradient(135deg, #1e2330 30%, #4f46e5 130%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.kl-hook { color: var(--kl-muted); font-size: 16px; max-width: 58ch; margin: 0 auto; }
.kl-block {
  background: var(--kl-bg); border: 1px solid var(--kl-border);
  border-radius: var(--kl-radius); padding: 24px 26px; margin: 18px 0;
  box-shadow: var(--kl-shadow);
}
.kl-block h2, .kl-block h3 { margin-top: 0; letter-spacing: -.01em; }
.kl-block code { background: var(--kl-accent-soft); color: #3730a3; padding: 1.5px 6px; border-radius: 6px; font-size: .88em; }
.kl-block strong { font-weight: 680; }
/* quiz */
.kl-quiz-q { font-weight: 640; font-size: 17px; }
.kl-quiz-opts { display: flex; flex-direction: column; gap: 9px; margin: 14px 0; }
.kl-quiz-opt {
  text-align: left; padding: 12px 16px; border: 1.5px solid var(--kl-border);
  border-radius: 11px; background: var(--kl-bg); cursor: pointer; font: inherit;
  transition: background .15s, border-color .15s, transform .1s, box-shadow .15s;
}
.kl-quiz-opt:hover { background: var(--kl-soft); border-color: #c8ccfb; transform: translateY(-1px); }
.kl-quiz-opt.is-correct { border-color: var(--kl-ok); background: var(--kl-ok-soft); }
.kl-quiz-opt.is-wrong { border-color: var(--kl-bad); background: var(--kl-bad-soft); }
.kl-quiz-opt.is-selected { border-color: var(--kl-accent); background: var(--kl-accent-soft); box-shadow: 0 0 0 3px rgba(79,70,229,.12); }
.kl-quiz-feedback { margin: 8px 0 0; font-size: 14.5px; padding: 10px 14px; border-radius: 10px; }
.kl-quiz-feedback.is-correct { color: #0b6e3f; background: var(--kl-ok-soft); }
.kl-quiz-feedback.is-wrong { color: #b42318; background: var(--kl-bad-soft); }
.kl-quiz-title { font-weight: 680; margin: 0 0 4px; font-size: 17px; }
.kl-quiz-progress { color: var(--kl-muted); font-size: 13px; font-variant-numeric: tabular-nums; font-weight: 600; }
.kl-quiz-input { width: 100%; padding: 11px 14px; border: 1.5px solid var(--kl-border); border-radius: 10px; font: inherit; transition: border-color .15s, box-shadow .15s; }
.kl-quiz-input:focus { outline: none; border-color: var(--kl-accent); box-shadow: 0 0 0 3px rgba(79,70,229,.14); }
.kl-quiz-actions { display: flex; gap: 10px; margin-top: 14px; }
.kl-quiz-submit, .kl-quiz-next, .kl-quiz-redo {
  font: inherit; font-weight: 620; padding: 9px 20px; border: none;
  border-radius: 10px; background: var(--kl-grad); color: #fff; cursor: pointer;
  box-shadow: 0 2px 10px rgba(79,70,229,.30); transition: transform .12s, box-shadow .15s, opacity .15s;
}
.kl-quiz-submit:hover, .kl-quiz-next:hover, .kl-quiz-redo:hover { transform: translateY(-1px); box-shadow: 0 5px 16px rgba(79,70,229,.36); }
.kl-quiz-next { background: var(--kl-bg); color: var(--kl-accent); box-shadow: inset 0 0 0 1.5px var(--kl-accent); }
.kl-quiz-submit:disabled { opacity: .45; cursor: default; box-shadow: none; transform: none; }
.kl-quiz-score { margin-top: 16px; font-size: 17px; font-weight: 680; display: flex; align-items: center; gap: 12px; }
.kl-quiz-redo { background: var(--kl-bg); color: var(--kl-accent); font-weight: 560; box-shadow: inset 0 0 0 1.5px var(--kl-accent); }
/* shared slider styling (param_sim / audio / interactive_demo) */
.kl-block input[type=range] {
  -webkit-appearance: none; appearance: none; height: 6px; border-radius: 999px;
  background: linear-gradient(90deg, var(--kl-accent), var(--kl-accent-2)); cursor: pointer; outline: none;
}
.kl-block input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none; width: 20px; height: 20px; border-radius: 50%;
  background: #fff; border: 2.5px solid var(--kl-accent); box-shadow: 0 2px 7px rgba(79,70,229,.4);
  cursor: pointer; transition: transform .12s;
}
.kl-block input[type=range]::-webkit-slider-thumb:hover { transform: scale(1.18); }
.kl-block input[type=range]::-moz-range-thumb {
  width: 18px; height: 18px; border-radius: 50%; background: #fff;
  border: 2.5px solid var(--kl-accent); box-shadow: 0 2px 7px rgba(79,70,229,.4); cursor: pointer;
}
/* param_sim */
.kl-ps-controls { display: flex; flex-direction: column; gap: 14px; }
.kl-ps-ctl { display: grid; grid-template-columns: 124px 1fr 60px; align-items: center; gap: 14px; }
.kl-ps-name { font-size: 14px; color: var(--kl-muted); font-weight: 560; }
.kl-ps-val { font-variant-numeric: tabular-nums; text-align: right; font-weight: 700; color: var(--kl-accent); }
.kl-ps-outputs { display: flex; flex-wrap: wrap; gap: 12px; margin: 18px 0; }
.kl-ps-out { background: var(--kl-accent-soft); border: 1px solid #dfe1fb; border-radius: 12px; padding: 10px 16px; }
.kl-ps-out span { color: var(--kl-muted); font-size: 12.5px; margin-right: 8px; }
.kl-ps-out strong { font-variant-numeric: tabular-nums; color: var(--kl-accent); font-size: 18px; }
.kl-ps-canvas { width: 100%; height: auto; background: var(--kl-bg); border: 1px solid var(--kl-border); border-radius: 12px; box-shadow: inset 0 0 0 1px rgba(255,255,255,.6); }
.kl-ps-explain { color: var(--kl-muted); font-size: 14.5px; }
/* callout */
.kl-callout { display: flex; gap: 13px; align-items: flex-start; border: none; border-left: 4px solid var(--kl-accent); background: linear-gradient(100deg, var(--kl-accent-soft), rgba(238,240,254,.25)); }
.kl-callout-icon { font-size: 20px; line-height: 1.5; }
.kl-callout-body > :first-child { margin-top: 0; }
.kl-callout-body > :last-child { margin-bottom: 0; }
.kl-callout-tip { border-left-color: var(--kl-ok); background: linear-gradient(100deg, var(--kl-ok-soft), rgba(231,246,236,.25)); }
.kl-callout-warning { border-left-color: #d9930a; background: linear-gradient(100deg, #fef6e7, rgba(254,246,231,.25)); }
.kl-callout-danger { border-left-color: var(--kl-bad); background: linear-gradient(100deg, var(--kl-bad-soft), rgba(253,235,236,.25)); }
/* section */
.kl-section { border: none; background: transparent; padding: 8px 0; border-bottom: 2px solid var(--kl-border); border-radius: 0; box-shadow: none; }
.kl-section-title { margin: 0; }
/* figure */
.kl-figure { text-align: center; }
.kl-figure img, .kl-figure svg { max-width: 100%; height: auto; border-radius: 10px; }
.kl-figure figcaption { color: var(--kl-muted); font-size: 13px; margin-top: 8px; }
/* code */
.kl-code-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.kl-code-lang { color: var(--kl-muted); font-size: 13px; }
.kl-code-copy { font: inherit; font-size: 13px; padding: 4px 12px; border: 1px solid var(--kl-border); border-radius: 8px; background: var(--kl-bg); cursor: pointer; transition: background .15s; }
.kl-code-copy:hover { background: var(--kl-soft); }
.kl-code pre { background: #0f1424; color: #e6e9f2; padding: 16px; border-radius: 12px; overflow: auto; margin: 0; font-size: 13.5px; }
.kl-code pre code { background: none; color: inherit; padding: 0; }
/* flashcards */
.kl-fc-card { min-height: 104px; border: 1.5px solid var(--kl-border); border-radius: 14px; padding: 22px; cursor: pointer; display: grid; place-items: center; text-align: center; transition: background .15s, border-color .15s, transform .12s, box-shadow .15s; }
.kl-fc-card:hover { background: var(--kl-soft); border-color: #c8ccfb; transform: translateY(-2px); box-shadow: var(--kl-shadow-lg); }
.kl-fc-back { display: none; color: var(--kl-accent); }
.kl-fc-card.is-flipped .kl-fc-front { display: none; }
.kl-fc-card.is-flipped .kl-fc-back { display: block; }
.kl-fc-nav, .kl-st-nav, .kl-anim-nav { display: flex; align-items: center; gap: 12px; justify-content: center; margin-top: 14px; }
.kl-fc-nav button, .kl-st-nav button, .kl-anim-nav button, .kl-tl-node { font: inherit; font-weight: 560; padding: 7px 16px; border: 1.5px solid var(--kl-border); border-radius: 999px; background: var(--kl-bg); cursor: pointer; transition: background .15s, border-color .15s; }
.kl-fc-nav button:hover, .kl-st-nav button:hover, .kl-anim-nav button:hover { border-color: var(--kl-accent); color: var(--kl-accent); }
.kl-fc-count, .kl-st-progress, .kl-anim-frame { color: var(--kl-muted); font-variant-numeric: tabular-nums; font-weight: 600; }
button:disabled { opacity: .4; cursor: default; }
/* step_through */
.kl-st-state { background: linear-gradient(180deg, #fbfcfe, var(--kl-soft)); border: 1px solid var(--kl-border); border-radius: 12px; padding: 18px; font-family: ui-monospace, "SF Mono", monospace; white-space: pre-wrap; font-size: 14.5px; }
.kl-st-explain { color: var(--kl-muted); margin-top: 10px; }
/* timeline */
.kl-tl-track { display: flex; gap: 10px; overflow-x: auto; padding-bottom: 8px; }
.kl-tl-node { display: flex; flex-direction: column; min-width: 116px; text-align: left; border-radius: 12px; }
.kl-tl-node.is-active { border-color: var(--kl-accent); background: var(--kl-accent-soft); }
.kl-tl-t { color: var(--kl-accent); font-size: 12px; font-weight: 600; }
.kl-tl-detail { margin-top: 12px; padding: 14px; background: var(--kl-soft); border-radius: 12px; }
/* interactive_demo */
.kl-id-controls { display: flex; flex-direction: column; gap: 12px; }
.kl-id-ctl { display: flex; align-items: center; gap: 14px; }
.kl-id-ctl > span { min-width: 124px; color: var(--kl-muted); font-size: 14px; font-weight: 560; }
.kl-id-outputs { display: flex; flex-wrap: wrap; gap: 12px; margin: 18px 0; }
.kl-id-out { background: var(--kl-accent-soft); border: 1px solid #dfe1fb; border-radius: 12px; padding: 10px 16px; }
.kl-id-out span { color: var(--kl-muted); font-size: 12.5px; margin-right: 8px; }
.kl-id-out strong { color: var(--kl-accent); font-size: 18px; }
.kl-id-explain { color: var(--kl-muted); font-size: 14.5px; }
/* animation */
.kl-anim-stage { background: linear-gradient(180deg, #fbfcfe, var(--kl-soft)); border: 1px solid var(--kl-border); border-radius: 12px; padding: 30px; text-align: center; min-height: 60px; font-size: 18px; }
/* concept_graph */
.kl-cg-canvas { width: 100%; height: auto; background: var(--kl-bg); border: 1px solid var(--kl-border); border-radius: 12px; cursor: pointer; }
/* audio */
.kl-au-canvas { width: 100%; height: auto; background: #0f1424; border: 1px solid var(--kl-border); border-radius: 12px; }
.kl-au-controls { display: flex; flex-direction: column; gap: 12px; margin: 16px 0; }
.kl-au-ctl { display: grid; grid-template-columns: 124px 1fr 60px; align-items: center; gap: 14px; }
.kl-au-name { font-size: 14px; color: var(--kl-muted); font-weight: 560; }
.kl-au-val { text-align: right; font-variant-numeric: tabular-nums; font-weight: 700; color: var(--kl-accent); }
.kl-au-bar { display: flex; align-items: center; gap: 14px; }
.kl-audio-play { font: inherit; font-weight: 620; padding: 10px 22px; border: none; border-radius: 999px; background: var(--kl-grad); color: #fff; cursor: pointer; box-shadow: 0 2px 10px rgba(79,70,229,.3); transition: transform .12s; }
.kl-audio-play:hover { transform: translateY(-1px); }
.kl-audio-play.is-playing { background: linear-gradient(135deg, var(--kl-warm), #fb923c); }
.kl-au-hint, .kl-au-explain { color: var(--kl-muted); font-size: 14.5px; }
/* manim — 3Blue1Brown-style rendered animation */
.kl-manim-fig { margin: 0; }
.kl-manim-video { width: 100%; height: auto; display: block; border-radius: 12px; background: #000; box-shadow: var(--kl-shadow); }
.kl-manim-cap { color: var(--kl-muted); font-size: 13px; margin: 10px 2px 0; text-align: center; }
.kl-manim-fallback { background: linear-gradient(180deg, #fbfcfe, var(--kl-soft)); border: 1.5px dashed var(--kl-border); border-radius: 12px; padding: 30px; text-align: center; color: var(--kl-muted); }
.kl-manim-note { font-size: 12px; margin: 8px 0 0; color: var(--kl-muted); }
/* user_note */
.kl-usernote-area { width: 100%; border: 1.5px solid var(--kl-border); border-radius: 12px; padding: 12px; font: inherit; resize: vertical; transition: border-color .15s; }
.kl-usernote-area:focus { outline: none; border-color: var(--kl-accent); }
/* deep_dive */
.kl-deepdive summary { cursor: pointer; font-weight: 640; }
/* ── card deck (one block at a time) ── */
.kl-deck { margin: 20px 0 4px; }
.kl-deck-viewport { overflow: hidden; transition: height .35s ease; }
.kl-deck-track { display: flex; align-items: flex-start; transition: transform .38s cubic-bezier(.4,0,.2,1); will-change: transform; }
.kl-card { flex: 0 0 100%; width: 100%; padding: 2px; }
.kl-card > .kl-block, .kl-card > details.kl-block { margin: 0; }
.kl-deck-nav { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 20px; }
.kl-deck-prev, .kl-deck-next {
  font: inherit; font-weight: 600; padding: 10px 20px; border: 1.5px solid var(--kl-border);
  border-radius: 999px; background: var(--kl-bg); color: var(--kl-fg); cursor: pointer;
  transition: background .15s, border-color .15s, transform .12s, box-shadow .15s;
}
.kl-deck-next { border-color: transparent; background: var(--kl-grad); color: #fff; box-shadow: 0 3px 12px rgba(79,70,229,.32); }
.kl-deck-next:hover { transform: translateY(-1px); box-shadow: 0 6px 18px rgba(79,70,229,.4); }
.kl-deck-prev:hover { background: var(--kl-soft); border-color: #c8ccfb; }
.kl-deck-prev:disabled, .kl-deck-next:disabled { opacity: .4; cursor: default; box-shadow: none; transform: none; }
.kl-deck-center { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.kl-deck-progress { color: var(--kl-muted); font-size: 13px; font-variant-numeric: tabular-nums; font-weight: 600; }
.kl-deck-dots { display: flex; gap: 7px; }
.kl-deck-dot { width: 9px; height: 9px; padding: 0; border-radius: 50%; border: 1.5px solid var(--kl-border); background: transparent; cursor: pointer; transition: background .15s, transform .15s, width .15s; }
.kl-deck-dot.is-active { background: var(--kl-grad); border-color: transparent; width: 22px; border-radius: 999px; }
.kl-deck-done { text-align: center; color: var(--kl-ok); font-size: 14px; font-weight: 600; margin-top: 10px; }
@media (prefers-reduced-motion: no-preference) {
  .kl-card > .kl-block { animation: kl-rise .45s cubic-bezier(.2,.7,.3,1) both; }
  @keyframes kl-rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
}
/* math — native MathML (Temml) and the pure-CSS fallback both styled here */
.kl-math math { font-size: 1.05em; font-style: normal; white-space: normal; }
.kl-math-display { display: block; }
.kl-math-display math { display: block; margin: 10px auto; font-size: 1.18em; }
math { font-family: "Latin Modern Math", "STIX Two Math", "Cambria Math", math, serif; }
/* inline math (pure-CSS fallback when Temml is absent) */
.kl-math { font-family: "Latin Modern Math", "Cambria Math", "Times New Roman", Georgia, serif; font-style: italic; white-space: nowrap; }
.kl-math .kl-mathrm { font-style: normal; }
.kl-math-display { display: block; text-align: center; font-size: 1.15em; margin: 10px 0; }
.kl-frac { display: inline-flex; flex-direction: column; vertical-align: -0.55em; text-align: center; font-size: .88em; margin: 0 .12em; }
.kl-frac .kl-num { border-bottom: 1px solid currentColor; padding: 0 .3em; }
.kl-frac .kl-den { padding: 0 .3em; }
.kl-sqrt-arg { border-top: 1px solid currentColor; padding: 0 .15em; margin-left: .05em; }
.kl-math sup, .kl-math sub { font-size: .72em; font-style: italic; }
/* generic fallback */
.kl-generic-tag { color: var(--kl-accent-2); font-size: 14px; }
.kl-generic pre { background: var(--kl-soft); padding: 12px; border-radius: 8px; overflow: auto; font-size: 13px; }
.kl-footer { margin-top: 32px; color: var(--kl-muted); font-size: 12px; text-align: center; }
"""


# Knowledge-card deck: shows one block at a time with prev/next + dots.
# A horizontal track (each card 100% wide) is translated into view, so every
# card keeps real layout width — canvas/clientWidth-based blocks render correctly
# even before they're shown. A ResizeObserver keeps the viewport height matched
# to the active card (so quiz feedback / disclosures grow it smoothly).
_DECK_JS = """
(function () {
  var deck = document.querySelector('[data-deck]');
  if (!deck) return;
  var track = deck.querySelector('.kl-deck-track');
  var viewport = deck.querySelector('.kl-deck-viewport');
  var cards = Array.prototype.slice.call(track.children);
  var prev = deck.querySelector('.kl-deck-prev');
  var next = deck.querySelector('.kl-deck-next');
  var prog = deck.querySelector('.kl-deck-progress');
  var dotsBox = deck.querySelector('.kl-deck-dots');
  var nav = deck.querySelector('.kl-deck-nav');
  var n = cards.length, idx = 0;
  if (n <= 1) { if (nav) nav.style.display = 'none'; return; }

  var dots = cards.map(function (_, i) {
    var d = document.createElement('button');
    d.className = 'kl-deck-dot'; d.type = 'button';
    d.setAttribute('aria-label', '第 ' + (i + 1) + ' 张');
    d.addEventListener('click', function () { go(i); });
    dotsBox.appendChild(d); return d;
  });

  function setHeight() { viewport.style.height = cards[idx].offsetHeight + 'px'; }
  function render() {
    track.style.transform = 'translateX(-' + (idx * 100) + '%)';
    prog.textContent = (idx + 1) + ' / ' + n;
    prev.disabled = idx === 0;
    next.textContent = idx === n - 1 ? '完成 ✓' : '下一张 ›';
    dots.forEach(function (d, i) { d.classList.toggle('is-active', i === idx); });
    setHeight();
  }
  function stopMedia() {
    // halt anything playing on the card we're leaving: Web-Audio blocks listen
    // for this event; also pause any real <audio>/<video> elements.
    try { window.dispatchEvent(new CustomEvent('knowling:stop-media')); } catch (e) {}
    deck.querySelectorAll('audio, video').forEach(function (m) { try { m.pause(); } catch (e) {} });
  }
  function go(i) { if (i !== idx) stopMedia(); idx = Math.max(0, Math.min(n - 1, i)); render(); }

  prev.addEventListener('click', function () { go(idx - 1); });
  next.addEventListener('click', function () { if (idx < n - 1) go(idx + 1); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft') go(idx - 1);
    else if (e.key === 'ArrowRight') go(idx + 1);
  });
  window.addEventListener('resize', setHeight);
  if (window.ResizeObserver) {
    var ro = new ResizeObserver(function () { setHeight(); });
    cards.forEach(function (c) { ro.observe(c); });
  }
  render();
  setTimeout(setHeight, 60); setTimeout(setHeight, 320);
})();
"""


def assemble_html(spec: KnowlingSpec, fragments: List[str], title: str) -> str:
    """Assemble block fragments into a single self-contained knowledge-card deck."""
    hook = spec.pedagogy.hook if spec.pedagogy else ""
    cards = "\n".join(f'<div class="kl-card">{frag}</div>' for frag in fragments)
    hook_html = f'<p class="kl-hook">{_html.escape(hook)}</p>' if hook else ""
    # Seam ④: expose the unit's kp_id so the (self-contained) quiz block can
    # report its result to an embedding host. A host may pre-set window.__KNOWLING__
    # (e.g. knowling_id) before load; we only fill kp_id if absent.
    kp_json = _json.dumps(spec.knowledge_point_id, ensure_ascii=False)
    ident = (
        "<script>window.__KNOWLING__=window.__KNOWLING__||{};"
        "if(!window.__KNOWLING__.kp_id)window.__KNOWLING__.kp_id=" + kp_json + ";</script>"
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(title)} · Knowling</title>
<style>{_CSS}</style>
{ident}
</head>
<body>
<main class="kl-doc">
  <header class="kl-header">
    <h1>{_html.escape(title)}</h1>
    {hook_html}
  </header>
  <div class="kl-deck" data-deck>
    <div class="kl-deck-viewport">
      <div class="kl-deck-track">
{cards}
      </div>
    </div>
    <nav class="kl-deck-nav">
      <button class="kl-deck-prev" type="button">‹ 上一张</button>
      <div class="kl-deck-center">
        <div class="kl-deck-dots"></div>
        <span class="kl-deck-progress"></span>
      </div>
      <button class="kl-deck-next" type="button">下一张 ›</button>
    </nav>
  </div>
  <footer class="kl-footer">Generated by Knowling · 自包含交互学习卡片</footer>
</main>
<script>{_DECK_JS}</script>
</body>
</html>"""
