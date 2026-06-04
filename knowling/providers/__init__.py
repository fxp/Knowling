"""Provider abstraction (design §3.1 #4, §11).

All LLM/VLM calls go through ``LLMProvider``. The default binding is GLM
(zhipu); when no API key is present we transparently fall back to the offline
``MockProvider`` so the skeleton runs out of the box.
"""

from .base import LLMProvider, Message, Completion
from .mock import MockProvider
from .zhipu import ZhipuProvider
from .factory import get_provider

__all__ = [
    "LLMProvider",
    "Message",
    "Completion",
    "MockProvider",
    "ZhipuProvider",
    "get_provider",
]
