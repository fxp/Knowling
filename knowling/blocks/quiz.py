"""``quiz`` block (design §7).

content_spec: { question, options[str], answer:int, explain }
QA invariants: choosing wrong shows the explanation; choosing right marks correct.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, jslit, scope as _scope

TYPE = "quiz"


def validate(content_spec: Dict[str, Any]) -> None:
    for k in ("question", "options", "answer"):
        if k not in content_spec:
            raise ValueError(f"quiz block requires content_spec.{k}")
    opts = content_spec["options"]
    if not isinstance(opts, list) or len(opts) < 2:
        raise ValueError("quiz options must be a list of >= 2 entries")
    ans = content_spec["answer"]
    if not isinstance(ans, int) or not (0 <= ans < len(opts)):
        raise ValueError("quiz answer must be a valid option index")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Interaction invariants (design §7): wrong→explain, right→mark correct."""
    bid = block.get("block_id", "")
    explain = block.get("content_spec", {}).get("explain", "")

    def has_options(html: str) -> bool:
        return f'data-block-id="{bid}"' in html and "kl-quiz-opt" in html

    def wrong_shows_explain(html: str) -> bool:
        seg = _scope(html, bid)
        return "is-wrong" in seg and (not explain or explain[:12] in seg)

    def right_marks_correct(html: str) -> bool:
        return "is-correct" in _scope(html, bid)

    return [
        {"id": f"{bid}.options", "description": "渲染出可点击的选项", "check": has_options,
         "gui_hint": "页面应展示该 quiz 的全部选项按钮"},
        {"id": f"{bid}.wrong_explains", "description": "选错时给出解释", "check": wrong_shows_explain,
         "gui_hint": "点击一个错误选项，应高亮为错并显示解释文本"},
        {"id": f"{bid}.right_correct", "description": "选对时标记正确", "check": right_marks_correct,
         "gui_hint": "点击正确选项，应高亮为正确"},
    ]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return (
        "Render this quiz as a self-contained HTML fragment with inline <script>.\n"
        "Behavior: clicking an option reveals whether it is correct; a wrong\n"
        "choice shows the explanation; a right choice marks it correct. State\n"
        "stays in the DOM (no localStorage). Wrap in\n"
        "<section class=\"kl-block kl-quiz\" data-block-id=\"%s\">.\n"
        "BlockSpec: %s\n" % (block.get("block_id", ""), jslit(block))
    )


def template(block: Dict[str, Any]) -> str:
    bid = esc(block.get("block_id", "quiz"))
    cs = block.get("content_spec", {})
    question: str = cs.get("question", "")
    options: List[str] = cs.get("options", [])
    answer: int = int(cs.get("answer", 0))
    explain: str = cs.get("explain", "")

    opt_html = "\n".join(
        f'<button class="kl-quiz-opt" data-i="{i}">{esc(o)}</button>'
        for i, o in enumerate(options)
    )
    return f'''<section class="kl-block kl-quiz" data-block-id="{bid}">
  <p class="kl-quiz-q">{esc(question)}</p>
  <div class="kl-quiz-opts">
{opt_html}
  </div>
  <p class="kl-quiz-feedback" hidden></p>
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var answer = {answer};
    var explain = {jslit(explain)};
    var fb = root.querySelector('.kl-quiz-feedback');
    root.querySelectorAll('.kl-quiz-opt').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        var i = parseInt(btn.dataset.i, 10);
        root.querySelectorAll('.kl-quiz-opt').forEach(function(b) {{
          b.classList.remove('is-correct', 'is-wrong');
        }});
        fb.hidden = false;
        if (i === answer) {{
          btn.classList.add('is-correct');
          fb.textContent = '✓ 正确！' + (explain ? ' ' + explain : '');
          fb.className = 'kl-quiz-feedback is-correct';
        }} else {{
          btn.classList.add('is-wrong');
          root.querySelector('.kl-quiz-opt[data-i="' + answer + '"]').classList.add('is-correct');
          fb.textContent = '✗ 再想想。' + (explain ? ' ' + explain : '');
          fb.className = 'kl-quiz-feedback is-wrong';
        }}
      }});
    }});
  }})();
  </script>
</section>'''
