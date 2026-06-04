"""``flashcards`` block (design §7) — flip + next.

content_spec: { cards: [{front, back}] }.
Invariants: can flip a card; can advance to next.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, jslit, count_tag, has_wiring, scope as _scope

TYPE = "flashcards"


def validate(content_spec: Dict[str, Any]) -> None:
    cards = content_spec.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("flashcards block requires non-empty content_spec.cards")
    for c in cards:
        if "front" not in c or "back" not in c:
            raise ValueError("each flashcard needs front and back")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def interactive(html: str) -> bool:
        seg = _scope(html, bid)
        return has_wiring(seg) and count_tag(seg, "<button") >= 1

    return [
        {"id": f"{bid}.interactive", "description": "卡片可翻面/切换", "check": interactive,
         "gui_hint": "点击应翻面并能切换到下一张"},
    ]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    return ("Render flashcards: a flippable card (click to flip front/back) plus "
            "prev/next controls. Inline <script>, component-local state. No external assets.")


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    bid = esc(block.get("block_id", "fc"))
    cards = cs.get("cards", [])
    return f'''<section class="kl-block kl-flashcards" data-block-id="{bid}">
  <div class="kl-fc-card kl-fc-flip">
    <div class="kl-fc-face kl-fc-front"></div>
    <div class="kl-fc-face kl-fc-back"></div>
  </div>
  <div class="kl-fc-nav">
    <button class="kl-fc-prev" type="button">上一张</button>
    <span class="kl-fc-count"></span>
    <button class="kl-fc-next" type="button">下一张</button>
  </div>
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var cards = {jslit(cards)};
    var i = 0, flipped = false;
    var card = root.querySelector('.kl-fc-card');
    var front = root.querySelector('.kl-fc-front');
    var back = root.querySelector('.kl-fc-back');
    var count = root.querySelector('.kl-fc-count');
    function render() {{
      front.textContent = cards[i].front;
      back.textContent = cards[i].back;
      card.classList.toggle('is-flipped', flipped);
      count.textContent = (i + 1) + ' / ' + cards.length;
    }}
    card.addEventListener('click', function() {{ flipped = !flipped; render(); }});
    root.querySelector('.kl-fc-prev').addEventListener('click', function() {{
      i = (i - 1 + cards.length) % cards.length; flipped = false; render();
    }});
    root.querySelector('.kl-fc-next').addEventListener('click', function() {{
      i = (i + 1) % cards.length; flipped = false; render();
    }});
    render();
  }})();
  </script>
</section>'''
