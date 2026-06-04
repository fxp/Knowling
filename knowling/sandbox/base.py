"""Sandbox interface + render result."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RenderResult:
    html: str
    ok: bool = True
    screenshot_path: Optional[str] = None  # PNG path, or None (static backend)
    console_errors: List[str] = field(default_factory=list)
    backend: str = "static"

    @property
    def has_screenshot(self) -> bool:
        return bool(self.screenshot_path)


class Sandbox(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def render_and_screenshot(self, html: str, label: str = "artifact") -> RenderResult:
        """Load the artifact HTML and capture render state."""

    def close(self) -> None:  # optional cleanup
        return None

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
