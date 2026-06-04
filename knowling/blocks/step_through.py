"""``step_through`` block (design §7, a Knowling 重心) — stepwise reasoning.

content_spec: { steps: [{state, explain}] }. Prev/Next walks proof/algorithm
states; the explanation updates with each step.
Invariant: next/prev changes the displayed state.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, jslit, count_tag, has_wiring, scope as _scope

TYPE = "step_through"


def validate(content_spec: Dict[str, Any]) -> None:
    steps = content_spec.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("step_through requires non-empty content_spec.steps")
    for s in steps:
        if "state" not in s:
            raise ValueError("each step needs a 'state'")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def has_nav(html: str) -> bool:
        return count_tag(_scope(html, bid), "<button") >= 1

    def reactive(html: str) -> bool:
        return has_wiring(_scope(html, bid))

    return [
        {"id": f"{bid}.nav", "description": "有上/下一步控件", "check": has_nav,
         "gui_hint": "应有上一步/下一步按钮"},
        {"id": f"{bid}.reactive", "description": "切换步骤改变状态", "check": reactive,
         "gui_hint": "点击下一步应改变显示的状态与解释"},
    ]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return ("Render a step-through: prev/next buttons walk an ordered list of "
            "(state, explain); the shown state + explanation update each step; show "
            "a progress indicator. Inline <script>, local state. No external assets.")


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    bid = esc(block.get("block_id", "st"))
    steps = cs.get("steps", [])
    return f'''<section class="kl-block kl-stepthrough" data-block-id="{bid}">
  <div class="kl-st-state"></div>
  <p class="kl-st-explain"></p>
  <div class="kl-st-nav">
    <button class="kl-st-prev" type="button">‹ 上一步</button>
    <span class="kl-st-progress"></span>
    <button class="kl-st-next" type="button">下一步 ›</button>
  </div>
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var steps = {jslit(steps)};
    var i = 0;
    var stateEl = root.querySelector('.kl-st-state');
    var explainEl = root.querySelector('.kl-st-explain');
    var prog = root.querySelector('.kl-st-progress');
    var prev = root.querySelector('.kl-st-prev');
    var next = root.querySelector('.kl-st-next');
    function render() {{
      stateEl.textContent = steps[i].state;
      explainEl.textContent = steps[i].explain || '';
      prog.textContent = (i + 1) + ' / ' + steps.length;
      prev.disabled = i === 0;
      next.disabled = i === steps.length - 1;
    }}
    prev.addEventListener('click', function() {{ if (i > 0) {{ i--; render(); }} }});
    next.addEventListener('click', function() {{ if (i < steps.length - 1) {{ i++; render(); }} }});
    render();
  }})();
  </script>
</section>'''
