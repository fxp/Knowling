"""Sandbox layer (design §6.1 step 0, L1 foundation).

Renders a self-contained artifact and (when a real browser is available)
captures a screenshot + console errors for the QA loop. Two backends:

  * ``PlaywrightSandbox`` — headless Chromium; real screenshot + console log
    capture. Used when ``playwright`` is importable.
  * ``StaticSandbox``     — no browser; structural-only "render". Lets the QA
    loop run fully offline (heuristic render/interact scoring).

``get_sandbox()`` picks Playwright if present, else Static.
"""

from .base import RenderResult, Sandbox
from .static_sandbox import StaticSandbox
from .factory import get_sandbox

__all__ = ["RenderResult", "Sandbox", "StaticSandbox", "get_sandbox"]
