"""Headless-Chromium sandbox via Playwright (optional dependency).

Captures a real screenshot + page console errors. Activated by the factory only
when ``playwright`` imports successfully and a browser is installed.

Install:  pip install "knowling[qa]"  &&  python -m playwright install chromium
"""

from __future__ import annotations

import os
import tempfile
from typing import List

from .base import RenderResult, Sandbox


class PlaywrightSandbox(Sandbox):
    name = "playwright"

    def __init__(self, viewport=(900, 700), timeout_ms: int = 8000) -> None:
        self.viewport = viewport
        self.timeout_ms = timeout_ms

    @staticmethod
    def available() -> bool:
        try:
            import playwright  # noqa: F401
            from playwright.sync_api import sync_playwright  # noqa: F401

            return True
        except Exception:
            return False

    def render_and_screenshot(self, html_str: str, label: str = "artifact") -> RenderResult:
        from playwright.sync_api import sync_playwright

        errors: List[str] = []
        shot_path = os.path.join(tempfile.gettempdir(), f"knowling-{label}.png")
        ok = True
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": self.viewport[0], "height": self.viewport[1]})
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.set_content(html_str, wait_until="networkidle", timeout=self.timeout_ms)
                page.screenshot(path=shot_path, full_page=True)
                browser.close()
        except Exception as e:  # pragma: no cover - env dependent
            ok = False
            errors.append(f"playwright error: {e}")
            shot_path = None
        return RenderResult(
            html=html_str,
            ok=ok and not errors,
            screenshot_path=shot_path,
            console_errors=errors,
            backend=self.name,
        )
