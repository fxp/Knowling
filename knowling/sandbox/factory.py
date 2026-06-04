"""Sandbox selection: Playwright if available, else Static fallback."""

from __future__ import annotations

import os

from .base import Sandbox
from .static_sandbox import StaticSandbox


def get_sandbox(name: str = "auto") -> Sandbox:
    name = (name or "auto").lower()
    if name == "auto":
        name = (os.environ.get("KNOWLING_SANDBOX") or "auto").lower()
    if name in ("auto", "playwright"):
        try:
            from .playwright_sandbox import PlaywrightSandbox

            if PlaywrightSandbox.available():
                return PlaywrightSandbox()
        except Exception:
            pass
        if name == "playwright":
            raise RuntimeError("playwright sandbox requested but not available")
    return StaticSandbox()
