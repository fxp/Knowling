"""``quiz`` block (design §7) — the assessment half of a Knowling.

Supports a single question or a multi-question set with scoring, and four
question types:
  * ``single``  — one correct option
  * ``multi``   — multiple correct options (exact-set match)
  * ``boolean`` — true / false (normalized to a 2-option single)
  * ``fill``    — free-text answer matched against answer + accept[] (case-insensitive)

content_spec (preferred):
  { "questions": [ {type, prompt, options?, answer, accept?, explain} ], "title"? }
content_spec (back-compat single):
  { "question", "options", "answer":int, "explain" }

QA invariants (design §7): an answer can be submitted; a wrong answer shows the
explanation; a right answer is marked correct.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, jslit, has_control, has_wiring, count_tag, scope as _scope
from ..schema.models import as_int

TYPE = "quiz"
_TYPES = {"single", "multi", "boolean", "fill"}


# ─────────────────────────── normalization ───────────────────────────


def _normalize(cs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a list of normalized questions (boolean → 2-option single)."""
    raw = cs.get("questions")
    if not raw:
        raw = [{
            "type": "single",
            "prompt": cs.get("question", ""),
            "options": cs.get("options", []),
            "answer": cs.get("answer", 0),
            "explain": cs.get("explain", ""),
        }]
    out: List[Dict[str, Any]] = []
    for q in raw:
        t = q.get("type", "single")
        prompt = q.get("prompt", q.get("question", ""))
        explain = q.get("explain", "")
        if t == "boolean":
            out.append({"type": "single", "prompt": prompt,
                        "options": ["正确", "错误"],
                        "answer": 0 if q.get("answer") else 1, "explain": explain})
        elif t == "multi":
            out.append({"type": "multi", "prompt": prompt,
                        "options": list(q.get("options", [])),
                        "answer": sorted(as_int(a) for a in q.get("answer", [])),
                        "explain": explain})
        elif t == "fill":
            out.append({"type": "fill", "prompt": prompt,
                        "answer": str(q.get("answer", "")),
                        "accept": [str(a) for a in q.get("accept", [])],
                        "explain": explain})
        else:  # single
            out.append({"type": "single", "prompt": prompt,
                        "options": list(q.get("options", [])),
                        "answer": as_int(q.get("answer", 0)), "explain": explain})
    return out


# ─────────────────────────── validation ───────────────────────────


def validate(content_spec: Dict[str, Any]) -> None:
    if not content_spec.get("questions") and "question" not in content_spec:
        raise ValueError("quiz block requires content_spec.questions or .question")
    questions = _normalize(content_spec)
    if not questions:
        raise ValueError("quiz needs at least one question")
    for i, q in enumerate(questions):
        t = q["type"]
        if t not in _TYPES and t != "single":
            raise ValueError(f"q{i}: unknown quiz type {t!r}")
        if not q.get("prompt"):
            raise ValueError(f"q{i}: missing prompt")
        if t == "fill":
            if not q.get("answer"):
                raise ValueError(f"q{i}: fill question needs an answer")
            continue
        opts = q.get("options", [])
        if not isinstance(opts, list) or len(opts) < 2:
            raise ValueError(f"q{i}: needs >= 2 options")
        if t == "multi":
            if not q["answer"] or any(not (0 <= a < len(opts)) for a in q["answer"]):
                raise ValueError(f"q{i}: multi answers must be valid option indices")
        else:
            if not (0 <= q["answer"] < len(opts)):
                raise ValueError(f"q{i}: answer must be a valid option index")


# ─────────────────────────── QA assertions ───────────────────────────


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Semantic (template-agnostic) interaction invariants."""
    bid = block.get("block_id", "")

    def has_answer_ui(html: str) -> bool:
        seg = _scope(html, bid)
        # ≥2 clickable options, or any input/select (single-choice/fill/multi)
        return count_tag(seg, "<button") >= 2 or "<input" in seg.lower() or "<select" in seg.lower()

    def judges(html: str) -> bool:
        # an answer must do *something* on interaction (check / score)
        return has_wiring(_scope(html, bid))

    return [
        {"id": f"{bid}.answer_ui", "description": "渲染出作答控件", "check": has_answer_ui,
         "gui_hint": "页面应展示可点击选项或输入框"},
        {"id": f"{bid}.judge", "description": "作答有判定反馈", "check": judges,
         "gui_hint": "提交/选择后应给出对错与解释"},
    ]


# ─────────────────────────── compile prompt ───────────────────────────


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return (
        "Render this quiz as a self-contained HTML fragment with inline <script>.\n"
        "Support single/multi/boolean/fill question types and, for multi-question\n"
        "sets, progress + a final score with retry. Submitting reveals correctness;\n"
        "a wrong answer shows the explanation. State stays in the DOM (no localStorage).\n"
        "Wrap in <section class=\"kl-block kl-quiz\" data-block-id=\"%s\">.\n"
        "BlockSpec: %s\n" % (block.get("block_id", ""), jslit(block))
    )


# ─────────────────────────── template ───────────────────────────


def template(block: Dict[str, Any]) -> str:
    bid = esc(block.get("block_id", "quiz"))
    cs = block.get("content_spec", {})
    questions = _normalize(cs)
    title = cs.get("title", "")
    title_html = f'<p class="kl-quiz-title">{esc(title)}</p>' if title else ""
    return f'''<section class="kl-block kl-quiz" data-block-id="{bid}">
  {title_html}
  <div class="kl-quiz-head"><span class="kl-quiz-progress"></span></div>
  <p class="kl-quiz-q"></p>
  <div class="kl-quiz-opts"></div>
  <p class="kl-quiz-feedback" hidden></p>
  <div class="kl-quiz-actions">
    <button class="kl-quiz-submit" type="button">提交</button>
    <button class="kl-quiz-next" type="button" hidden></button>
  </div>
  <div class="kl-quiz-score" hidden></div>
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var questions = {jslit(questions)};
    var many = questions.length > 1;
    var idx = 0, score = 0, locked = false, selected = null;
    var qBox = root.querySelector('.kl-quiz-q');
    var optBox = root.querySelector('.kl-quiz-opts');
    var fb = root.querySelector('.kl-quiz-feedback');
    var submit = root.querySelector('.kl-quiz-submit');
    var next = root.querySelector('.kl-quiz-next');
    var prog = root.querySelector('.kl-quiz-progress');
    var scoreBox = root.querySelector('.kl-quiz-score');

    function render() {{
      var q = questions[idx];
      locked = false; selected = q.type === 'multi' ? {{}} : null;
      qBox.textContent = q.prompt;
      fb.hidden = true; fb.className = 'kl-quiz-feedback';
      next.hidden = true; submit.hidden = false; submit.disabled = false;
      scoreBox.hidden = true;
      prog.textContent = many ? (idx + 1) + ' / ' + questions.length : '';
      optBox.innerHTML = '';
      if (q.type === 'fill') {{
        var inp = document.createElement('input');
        inp.type = 'text'; inp.className = 'kl-quiz-input'; inp.placeholder = '输入答案…';
        inp.addEventListener('keydown', function(e) {{ if (e.key === 'Enter' && !locked) judge(); }});
        optBox.appendChild(inp);
      }} else {{
        q.options.forEach(function(o, i) {{
          var btn = document.createElement('button');
          btn.type = 'button'; btn.className = 'kl-quiz-opt'; btn.dataset.i = i; btn.textContent = o;
          btn.addEventListener('click', function() {{
            if (locked) return;
            if (q.type === 'multi') {{
              if (selected[i]) {{ delete selected[i]; btn.classList.remove('is-selected'); }}
              else {{ selected[i] = 1; btn.classList.add('is-selected'); }}
            }} else {{
              selected = i;
              optBox.querySelectorAll('.kl-quiz-opt').forEach(function(b) {{ b.classList.remove('is-selected'); }});
              btn.classList.add('is-selected');
            }}
          }});
          optBox.appendChild(btn);
        }});
      }}
    }}

    function judge() {{
      var q = questions[idx], correct = false;
      optBox.querySelectorAll('.kl-quiz-opt').forEach(function(b) {{ b.classList.remove('is-selected'); }});
      if (q.type === 'fill') {{
        var val = (optBox.querySelector('.kl-quiz-input').value || '').trim().toLowerCase();
        var accept = [String(q.answer)].concat(q.accept || []).map(function(s) {{ return String(s).trim().toLowerCase(); }});
        correct = accept.indexOf(val) >= 0;
      }} else if (q.type === 'multi') {{
        var sel = Object.keys(selected).map(Number).sort(function(a, b) {{ return a - b; }});
        var ans = (q.answer || []).slice();
        correct = sel.length === ans.length && sel.every(function(v, k) {{ return v === ans[k]; }});
        optBox.querySelectorAll('.kl-quiz-opt').forEach(function(b) {{
          var i = parseInt(b.dataset.i, 10);
          if (ans.indexOf(i) >= 0) b.classList.add('is-correct');
          else if (selected[i]) b.classList.add('is-wrong');
        }});
      }} else {{
        correct = selected === q.answer;
        optBox.querySelectorAll('.kl-quiz-opt').forEach(function(b) {{
          var i = parseInt(b.dataset.i, 10);
          if (i === q.answer) b.classList.add('is-correct');
          else if (i === selected) b.classList.add('is-wrong');
        }});
      }}
      locked = true; submit.disabled = true;
      if (correct) score++;
      fb.hidden = false;
      fb.className = 'kl-quiz-feedback ' + (correct ? 'is-correct' : 'is-wrong');
      fb.textContent = (correct ? '✓ 正确！' : '✗ 再想想。') + (q.explain ? ' ' + q.explain : '');
      if (many) {{ next.hidden = false; next.textContent = idx < questions.length - 1 ? '下一题' : '查看成绩'; }}
    }}

    function showScore() {{
      optBox.innerHTML = ''; qBox.textContent = ''; fb.hidden = true;
      submit.hidden = true; next.hidden = true; prog.textContent = '';
      scoreBox.hidden = false;
      scoreBox.innerHTML = '成绩 ' + score + ' / ' + questions.length +
        ' <button type="button" class="kl-quiz-redo">重做</button>';
      scoreBox.querySelector('.kl-quiz-redo').addEventListener('click', function() {{
        idx = 0; score = 0; render();
      }});
    }}

    submit.addEventListener('click', judge);
    next.addEventListener('click', function() {{
      if (idx < questions.length - 1) {{ idx++; render(); }} else showScore();
    }});
    render();
  }})();
  </script>
</section>'''
