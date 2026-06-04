"""Shared helpers for block templates: escaping + tiny Markdown subset."""

from __future__ import annotations

import html
import json
import re
from typing import Any


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def jslit(value: Any) -> str:
    """Serialize a Python value as a safe JS literal (for inline <script>)."""
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


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
        t = esc(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
        t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        return t

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
