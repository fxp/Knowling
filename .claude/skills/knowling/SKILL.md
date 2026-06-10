---
name: knowling
description: >-
  Generate a self-contained, interactive teaching/learning card for ONE small,
  specific knowledge point — narrative + explorable demo (param_sim / step_through /
  interactive_demo) + quiz, optionally with audio or a 3Blue1Brown-style manim
  animation, all in a single dependency-free .html. Use when the user wants to
  "讲解/explain a concept as an interactive card", "做个可交互的学习组件/explorable",
  "把 XX 讲清楚做成可玩的演示", "生成知识点讲解内容", "用 Knowling 生成", or asks for a
  learning/teaching card for a concept. SKIP whole-course / whole-book generation,
  topic decomposition, knowledge-graph navigation, or plain static article writing.
---

# Knowling — knowledge point → interactive teaching card

Turns **one** clearly-scoped knowledge point into a structured blueprint (KnowlingSpec)
→ compiled blocks → a **single self-contained `.html`** (inline CSS/JS, no external
deps). Optionally runs a three-dimensional QA loop (render / interaction / pedagogy)
so only cards that pass are marked `ready`.

## When to use / skip
- ✅ A specific concept the user wants to *learn or teach interactively*: "链式法则",
  "TCP 三次握手", "二次函数系数 a 的作用", "棱锥体积为什么是 1/3".
- ✅ Prefer **explorable** output — drag a quantity and watch the result change.
- ❌ Not for: an entire course/book, splitting a big topic into many points, a
  knowledge-graph/navigation shell, or a plain prose article. Keep it to one point.

## Prerequisites
- Run from the Knowling repo root (this skill calls its CLI).
- `ZHIPU_API_KEY` in env → real GLM content; **unset → offline Mock** (templated,
  low-fidelity, fine for a dry run). The repo's `.env` is auto-used by the shell.
- Optional: `[manim]` toolchain (`.venv-manim` + ffmpeg) for `--allow-manim`; absent
  → manim blocks degrade to a captioned placeholder (never crashes).

## Primary workflow — `gen` (plan → compile → QA → assemble)

```bash
python3 -m knowling.cli gen "<知识点标题>" \
  --description "<一句话精确界定这个点>" \
  --objectives "目标1,目标2" \
  --difficulty core --audience "初三学生" \
  -o ./out/            # file or dir/; the produced .html is the deliverable
```

Add `--allow-manim` for a 3Blue1Brown-style rendered animation (geometry / area
models / identities). Add `--no-qa` to skip the (slow) QA loop for a quick draft.
Use `-f json` to get a line-delimited **event stream** (plan/compile/qa/done) for
programmatic use; the final `done` event carries `status` + `entry` (path).

**Result handling:** the output is a self-contained `.html` — hand the path to the
user to open in a browser, or read it back. `status`: `ready` (passed QA) ·
`qa_failed` (rendered but didn't pass) · `draft` (QA skipped via `--no-qa`).

## Options (gen / plan)
| Flag | Meaning |
|---|---|
| `--description` | one line that precisely scopes the point (drives everything) |
| `--objectives` | comma-separated learning objectives |
| `--difficulty` | `intro` · `core` (default) · `advanced` |
| `--audience` | e.g. "初二学生" / "高中生" / "本科生" |
| `--ground PATH` | grounding file (local text/md) to anchor facts; repeatable |
| `--allow-manim` | let the planner add one manim animation (needs `[manim]`) |
| `--no-qa` | skip the three-dimensional QA loop (status stays `draft`) |
| `--provider` | `auto` (default) · `zhipu` · `mock` |
| `--compile-mode` | `template` (consistent, default) · `codegen` (LLM per block) |
| `-o, --output` | output path (file or `dir/`) |

## Other subcommands
- **Blueprint review:** `knowling plan "<点>" -o out/x.spec.json` → edit → `knowling compile out/x.spec.json --title "<点>" -o out/x.html`.
- **Chat rewrite** (one fixed card → next): `knowling refine out/x.spec.json "太难了，给初中生版本" --title "<点>" -o out/x2.html`.
- **Studio** (card + AI chat, live re-gen): `knowling serve "<点>" --audience 高中生`.
- **List block types:** `knowling blocks`.

## HTTP API (for hosts/agents over the network)
Same capability as a service: `python3 -m knowling.server --port 8765` →
`POST /v1/generate {kp, qa?, allow_manim?, ground?}` returns `{knowling, html}`.
See `docs/api.md` (auth, endpoints) and `deploy/cloudflare.md`.

## Guardrails
- **One knowledge point per card.** If the user gives a broad topic, narrow it to a
  single point (or ask which sub-point) before generating — don't try to cover a
  whole syllabus in one card.
- Output is always a single self-contained HTML — never pull in external runtimes.
- For deeper design/internals see `knowling-design.md`; block list via `knowling blocks`.
