# Knowling HTTP API

Zero-dep stdlib HTTP service over the engine (seam contract §⑤ / ROADMAP P4), so a
host orchestrator (the adaptive-learning layer) can drive Knowling units over HTTP.

## Run

```bash
# offline (no key) → MockProvider; with a key → real GLM
export ZHIPU_API_KEY=sk-...            # optional
python -m knowling.server --port 8765  # or, after `pip install -e .`: knowling-api --port 8765
```

`GET /v1/health` → `{ok, version, provider, manim}`.

## Endpoints

All JSON. POST bodies are JSON objects. CORS is open (`*`) for browser frontends.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/v1/health` | — | `{ok, version, provider, manim}` |
| GET | `/v1/blocks` | — | `{blocks: [...]}` |
| POST | `/v1/plan` | `{kp, ground?, allow_manim?}` | `{spec}` |
| POST | `/v1/generate` | `{kp, qa?, allow_manim?, ground?}` | `{knowling, html}` |
| POST | `/v1/compile` | `{spec, kp, qa?}` | `{knowling, html}` |
| POST | `/v1/refine` | `{spec, kp, instruction}` | `{knowling, html, summary, changes}` |
| POST | `/v1/reteach` | `{spec, kp, quiz}` | `{knowling, html, summary}` |
| POST | `/v1/quiz-eval` | `{kp_id, quiz, knowling_id?, pass_threshold?}` | `{mastery}` |

### Common request fields
- `provider`: `"auto"` (default) · `"zhipu"` · `"mock"`.
- `qa`: bool, default **false** (QA is slow + needs a browser/VLM; opt in).
- `allow_manim`: bool, default false — let the planner add one 3B1B-style animation
  block (needs the `[manim]` toolchain; degrades to a placeholder otherwise).
- `ground`: list of grounding snippets (strings).

### Key objects
- `kp` = `KnowledgePoint` (`{id, title, description?, learning_objectives?, difficulty?,
  audience?, curriculum?}`); `id` + `title` required.
- `knowling.html` (and the top-level `html` field) is the **self-contained** artifact.
- `quiz` = `QuizOutcome` (`{total, correct, per_question?, wrong_tags?}`) — the same
  shape the card's `knowling:quiz-result` event emits.
- `mastery` = `MasteryResult` (`{kp_id, score, passed, level, ...}`) — feeds graph lighting.

## Examples

```bash
# health
curl -s localhost:8765/v1/health

# blueprint only
curl -s -X POST localhost:8765/v1/plan \
  -H 'Content-Type: application/json' \
  -d '{"kp":{"id":"math.slope","title":"一次函数的斜率","description":"k 表示倾斜程度"}}'

# full card (self-contained HTML in .html)
curl -s -X POST localhost:8765/v1/generate \
  -H 'Content-Type: application/json' \
  -d '{"kp":{"id":"math.slope","title":"一次函数的斜率"},"allow_manim":true}'

# quiz failed → re-teach an easier card for the same KP
curl -s -X POST localhost:8765/v1/reteach \
  -H 'Content-Type: application/json' \
  -d '{"kp":{"id":"math.slope","title":"斜率"},"spec":{...},"quiz":{"total":5,"correct":1}}'

# turn a quiz result into a mastery signal (graph lighting)
curl -s -X POST localhost:8765/v1/quiz-eval \
  -H 'Content-Type: application/json' \
  -d '{"kp_id":"math.slope","quiz":{"total":5,"correct":5}}'
```

## Notes
- Synchronous: `generate` with `qa:true` and/or `allow_manim:true` can take tens of
  seconds to minutes (real model + render). For fast calls use the defaults.
- Errors return `{error}` with 400 (bad request) / 404 (no route) / 500.
