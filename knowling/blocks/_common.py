"""Shared helpers for block templates: escaping + tiny Markdown subset."""

from __future__ import annotations

import html
import json
import re
from typing import Any

from ._math import render, split_math


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def _render_with_math(text: str, markdown: bool) -> str:
    """Render text that may contain $…$ math, optionally with inline markdown.

    Math is rendered first into placeholder tokens, so markdown emphasis that
    *wraps* a math span (e.g. ``**$a$**``) still works, and escaping never
    touches the rendered math HTML."""
    maths = []
    parts = []
    for seg, is_math, display in split_math(text):
        if is_math:
            maths.append(render(seg, display))
            parts.append(f"\x00{len(maths) - 1}\x00")
        else:
            parts.append(seg)
    s = esc("".join(parts))
    if markdown:
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return re.sub("\x00(\\d+)\x00", lambda m: maths[int(m.group(1))], s)


def mathspan(s: Any) -> str:
    """Escape plain text AND render inline/display $…$ math (self-contained).

    Use instead of esc() for any learner-facing field where LLMs may write LaTeX
    (explanations, labels, quiz text). Plain text with no math just gets escaped."""
    return _render_with_math("" if s is None else str(s), markdown=False)


def jslit(value: Any) -> str:
    """Serialize a Python value as a safe JS literal (for inline <script>)."""
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


# ── semantic interaction predicates (template-agnostic QA signals) ──
# Assertions check *behavior*, not our class names, so LLM-generated blocks that
# use their own markup still pass as long as they have real controls + JS wiring.

def has_control(seg: str) -> bool:
    low = seg.lower()
    return any(t in low for t in ("<input", "<button", "<select", "<textarea"))


def has_wiring(seg: str) -> bool:
    """Evidence of interactivity: a JS event handler is attached."""
    low = seg.lower()
    return any(t in low for t in (
        "addeventlistener", "oninput=", "onclick=", "onchange=", "onkeydown=", "onkeyup=",
    ))


def count_tag(seg: str, tag: str) -> int:
    return seg.lower().count(tag.lower())


def scope(html: str, block_id: str) -> str:
    """Return the substring of ``html`` belonging to one block (by data-block-id).

    From the block's opening tag to the next boundary: a *different* block's tag,
    or the deck chrome (nav/footer) that follows the last card. A block's own id
    recurs inside its <script>, so same-id markers are skipped. Bounding at the
    deck chrome prevents the trailing deck <script> from leaking into the last
    block's scope. Used by static QA assertions.
    """
    if not block_id:
        return html
    marker = f'data-block-id="{block_id}"'
    start = html.find(marker)
    if start == -1:
        return ""
    tag_start = html.rfind("<", 0, start)
    after = start + len(marker)
    rest = html[after:]

    boundary = len(rest)  # default: EOF
    for m in re.finditer(r'data-block-id="([^"]*)"', rest):
        if m.group(1) != block_id:
            boundary = min(boundary, m.start())
            break
    # also stop at the deck shell that trails the final card
    for sentinel in ('class="kl-deck-nav"', "class='kl-deck-nav'", "<footer"):
        p = rest.find(sentinel)
        if p != -1:
            boundary = min(boundary, p)
    end = html.rfind("<", 0, after + boundary)
    return html[tag_start:end] if end > tag_start else html[tag_start:after + boundary]


def mini_markdown(md: str) -> str:
    """Intentionally tiny MD→HTML: headings, bold, italic, inline code, lists,
    paragraphs. Enough for P0 text/callout blocks without a Markdown dep."""
    lines = md.splitlines()
    out = []
    in_ul = False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    def inline(t: str) -> str:
        return _render_with_math(t, markdown=True)

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_ul()
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            close_ul()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue
        if re.match(r"^[-*]\s+", line):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            item = re.sub(r"^[-*]\s+", "", line)
            out.append("<li>" + inline(item) + "</li>")
            continue
        close_ul()
        out.append(f"<p>{inline(line)}</p>")
    close_ul()
    return "\n".join(out)
