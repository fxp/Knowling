"""Provider base types.

A ``task`` hint travels with every call (``"plan"`` | ``"compile_block"`` | …).
Real providers ignore it; the offline ``MockProvider`` branches on it to return
something sensible without a model.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

Message = Dict[str, str]  # {"role": "system"|"user"|"assistant", "content": ...}


@dataclass
class Completion:
    """Result of one provider call, with token accounting for cost audit."""

    text: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    raw: Optional[Dict[str, Any]] = None


class LLMProvider(abc.ABC):
    """Unified LLM interface. Implementations: ZhipuProvider, MockProvider."""

    name: str = "base"

    def __init__(self, model: str, **opts: Any) -> None:
        self.model = model
        self.opts = opts

    @abc.abstractmethod
    def complete(
        self,
        messages: List[Message],
        *,
        task: str = "generic",
        temperature: float = 0.6,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Completion:
        """Return a single completion for a chat-style message list."""

    # convenience -------------------------------------------------------
    def chat(self, system: str, user: str, **kwargs: Any) -> Completion:
        msgs: List[Message] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user})
        return self.complete(msgs, **kwargs)
