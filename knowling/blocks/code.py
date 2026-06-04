"""``code`` block (design §7) — code listing with copy button.

content_spec: { lang, code, runnable? }. P2 ships syntax-neutral display + copy.
A real run-sandbox (Shiki/runnable) is a later enhancement.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._common import esc, jslit, scope as _scope

TYPE = "code"


def validate(content_spec: Dict[str, Any]) -> None:
    if "code" not in content_spec:
        raise ValueError("code block requires content_spec.code")


def qa_assertions(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    bid = block.get("block_id", "")

    def has_copy(html: str) -> bool:
        return "kl-code-copy" in _scope(html, bid)

    return [{"id": f"{bid}.copy", "description": "提供复制按钮", "check": has_copy,
             "gui_hint": "点击复制按钮应复制代码"}]


def compile_prompt(block: Dict[str, Any], kp: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    return (f"Render a code block (lang={cs.get('lang','')}) in <pre><code> with a "
            "copy-to-clipboard button. Inline <script> only. No external assets.")


def template(block: Dict[str, Any]) -> str:
    cs = block.get("content_spec", {})
    bid = esc(block.get("block_id", "code"))
    lang = esc(cs.get("lang", ""))
    code = cs.get("code", "")
    return f'''<section class="kl-block kl-code" data-block-id="{bid}">
  <div class="kl-code-head"><span class="kl-code-lang">{lang}</span>
    <button class="kl-code-copy" type="button">复制</button></div>
  <pre><code>{esc(code)}</code></pre>
  <script>
  (function() {{
    var root = document.querySelector('[data-block-id="{bid}"]');
    var btn = root.querySelector('.kl-code-copy');
    var src = {jslit(code)};
    btn.addEventListener('click', function() {{
      navigator.clipboard && navigator.clipboard.writeText(src);
      btn.textContent = '已复制'; setTimeout(function() {{ btn.textContent = '复制'; }}, 1200);
    }});
  }})();
  </script>
</section>'''
