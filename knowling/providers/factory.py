"""Provider selection (design §3.1 #4).

Resolution order:
  1. explicit ``name`` argument / ``KNOWLING_PROVIDER`` env
  2. ``"auto"`` (default): GLM if a key is present, else mock
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional

from .base import LLMProvider
from .mock import MockProvider
from .zhipu import ZhipuProvider

# default model per pipeline role (design §6.3 cost separation)
DEFAULT_MODELS = {
    "zhipu": {
        "plan": "glm-4.6",
        "compile": "glm-4.6",
        "render_vlm": "glm-4v",
        "gui": "glm-4-air",
        "judge": "glm-4.6",
    },
    "mock": {k: "mock-1" for k in ("plan", "compile", "render_vlm", "gui", "judge")},
}


def get_provider(
    name: str = "auto",
    role: str = "plan",
    model: Optional[str] = None,
    quiet: bool = False,
    **opts: Any,
) -> LLMProvider:
    name = (name or "auto").lower()
    if name == "auto":
        name = (os.environ.get("KNOWLING_PROVIDER") or "auto").lower()
    if name == "auto":
        name = "zhipu" if ZhipuProvider.available() else "mock"
        if name == "mock" and not quiet:
            print(
                "[knowling] no ZHIPU_API_KEY/GLM_API_KEY found → using offline MockProvider.",
                file=sys.stderr,
            )

    if name == "zhipu":
        mdl = model or DEFAULT_MODELS["zhipu"].get(role, "glm-4.6")
        return ZhipuProvider(model=mdl, **opts)
    if name == "mock":
        return MockProvider(model=model or "mock-1", **opts)
    raise ValueError(f"unknown provider {name!r} (zhipu | mock | auto)")
