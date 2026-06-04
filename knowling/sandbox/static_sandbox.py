"""No-browser sandbox — structural render only (offline QA path).

Cannot screenshot or execute JS, but performs a lightweight HTML well-formedness
check so the render dimension still has a real signal without a browser.
"""

from __future__ import annotations

import html.parser
from typing import List

from .base import RenderResult, Sandbox


class _Checker(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: List[str] = []
        self.tags = 0

    def error(self, message):  # pragma: no cover - py<3.10 hook
        self.errors.append(message)

    def handle_starttag(self, tag, attrs):
        self.tags += 1


class StaticSandbox(Sandbox):
    name = "static"

    def render_and_screenshot(self, html_str: str, label: str = "artifact") -> RenderResult:
        checker = _Checker()
        ok = True
        errors: List[str] = []
        try:
            checker.feed(html_str)
        except Exception as e:  # malformed markup
            ok = False
            errors.append(f"parse error: {e}")
        if checker.tags < 3:
            ok = False
            errors.append("too few elements rendered")
        return RenderResult(
            html=html_str,
            ok=ok,
            screenshot_path=None,
            console_errors=errors,
            backend=self.name,
        )
