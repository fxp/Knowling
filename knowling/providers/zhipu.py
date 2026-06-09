"""GLM (zhipu) provider — the default binding (design §11).

Talks to the OpenAI-compatible chat endpoint at
``https://open.bigmodel.cn/api/paas/v4/chat/completions`` using only stdlib
``urllib`` (no ``requests`` dependency). API key from ``ZHIPU_API_KEY`` or
``GLM_API_KEY``.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, List, Optional

from .base import Completion, LLMProvider, Message

DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

# Rough public list price (USD per 1K tokens) for cost estimation only.
_PRICE_PER_1K = {
    "glm-5.1": (0.0006, 0.0022),
    "glm-5v-turbo": (0.0002, 0.0002),
    "glm-4.6": (0.0006, 0.0022),
    "glm-4-air": (0.00007, 0.00007),
    "glm-4v": (0.0006, 0.0006),
}


class ProviderError(RuntimeError):
    pass


class ZhipuProvider(LLMProvider):
    name = "zhipu"

    def __init__(
        self,
        model: str = "glm-5.1",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        **opts: Any,
    ) -> None:
        super().__init__(model, **opts)
        self.api_key = api_key or os.environ.get("ZHIPU_API_KEY") or os.environ.get("GLM_API_KEY")
        self.base_url = (base_url or os.environ.get("ZHIPU_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else float(os.environ.get("ZHIPU_TIMEOUT", "300"))

    @classmethod
    def available(cls) -> bool:
        return bool(os.environ.get("ZHIPU_API_KEY") or os.environ.get("GLM_API_KEY"))

    def _cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        pin, pout = _PRICE_PER_1K.get(model.lower(), (0.0, 0.0))
        return round(prompt_tokens / 1000 * pin + completion_tokens / 1000 * pout, 6)

    def complete(
        self,
        messages: List[Message],
        *,
        task: str = "generic",
        temperature: float = 0.6,
        max_tokens: int = 4096,
        thinking: Optional[str] = "disabled",  # "disabled" | "enabled" | None(API default)
        **kwargs: Any,
    ) -> Completion:
        if not self.api_key:
            raise ProviderError(
                "ZhipuProvider needs ZHIPU_API_KEY / GLM_API_KEY. "
                "Unset → use MockProvider (factory falls back automatically)."
            )
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # GLM-5 are reasoning models; for structured/code output we disable
        # thinking so reasoning tokens don't starve & truncate the answer.
        if thinking:
            payload["thinking"] = {"type": thinking}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        # Retry transient failures (connection resets, timeouts, 429/5xx) — the
        # proxy/edge can be flaky; one drop shouldn't fail a whole generation.
        body = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:  # pragma: no cover - network
                detail = e.read().decode("utf-8", "ignore")
                if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise ProviderError(f"GLM HTTP {e.code}: {detail}") from e
            except urllib.error.URLError as e:  # pragma: no cover - network
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise ProviderError(f"GLM connection failed: {e.reason}") from e

        msg = body["choices"][0]["message"]
        # GLM-5 reasoning models may leave content empty and put text in
        # reasoning_content; fall back so JSON extraction still has something.
        choice = msg.get("content") or msg.get("reasoning_content") or ""
        usage = body.get("usage", {})
        pt = int(usage.get("prompt_tokens", 0))
        ct = int(usage.get("completion_tokens", 0))
        return Completion(
            text=choice,
            model=self.model,
            provider=self.name,
            prompt_tokens=pt,
            completion_tokens=ct,
            cost_usd=self._cost(self.model, pt, ct),
            raw=body,
        )
