"""Retriever — optional RAG grounding (design §5 ③, §3.1 D7).

Resolves a KnowledgePoint's ``source_refs`` into grounding chunks that anchor
planning, compilation, and the pedagogy judge to real material (anti-hallucination).

P2 ships a zero-dependency ``SimpleRetriever``:
  * inline ``snippet`` on a SourceRef → used directly
  * ``uri`` pointing at a local text/markdown file → read and split into paragraphs
  * optional keyword ranking against the knowledge point (top-k)

A LlamaIndex-backed retriever (DeepTutor parity) is an optional adapter; importing
it without the dep raises a clear install hint rather than failing silently.
"""

from __future__ import annotations

import abc
import os
import re
from dataclasses import dataclass
from typing import List, Optional

from ..schema import SourceRef


@dataclass
class GroundingChunk:
    source_id: str
    text: str
    title: Optional[str] = None
    score: float = 0.0

    def to_prompt(self) -> str:
        head = f"[{self.title or self.source_id}]"
        return f"{head} {self.text}".strip()


def format_grounding(chunks: List[GroundingChunk]) -> str:
    """Render chunks into a prompt-ready block (or '' if none)."""
    if not chunks:
        return ""
    return "\n".join(f"- {c.to_prompt()}" for c in chunks)


def _tokens(s: str) -> List[str]:
    return [t for t in re.split(r"[\s，,。、.;；:：]+", s.lower()) if len(t) >= 2]


class Retriever(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def fetch(
        self, source_refs: List[SourceRef], query: str = "", top_k: int = 6
    ) -> List[GroundingChunk]:
        ...


class SimpleRetriever(Retriever):
    name = "simple"

    def __init__(self, max_chars: int = 600) -> None:
        self.max_chars = max_chars

    def _load_text(self, ref: SourceRef) -> List[str]:
        if ref.snippet:
            return [ref.snippet]
        uri = ref.uri or ""
        path = uri[7:] if uri.startswith("file://") else uri
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    raw = f.read()
            except Exception:
                return []
            # split into paragraphs
            return [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
        return []

    def fetch(
        self, source_refs: List[SourceRef], query: str = "", top_k: int = 6
    ) -> List[GroundingChunk]:
        q = set(_tokens(query))
        chunks: List[GroundingChunk] = []
        for ref in source_refs or []:
            for para in self._load_text(ref):
                text = para[: self.max_chars]
                score = 0.0
                if q:
                    pt = set(_tokens(text))
                    score = len(q & pt) / (len(q) or 1)
                chunks.append(GroundingChunk(source_id=ref.id, text=text,
                                             title=ref.title, score=score))
        if q:
            chunks.sort(key=lambda c: c.score, reverse=True)
        return chunks[:top_k]


def get_retriever(name: str = "auto", **opts) -> Retriever:
    name = (name or "auto").lower()
    if name in ("auto", "simple"):
        return SimpleRetriever(**opts)
    if name == "llamaindex":
        try:
            import llama_index  # noqa: F401
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "llamaindex retriever requested but llama-index is not installed: "
                'pip install "knowling[rag]"'
            ) from e
        # adapter to be implemented when a vector store is configured
        raise NotImplementedError("LlamaIndex retriever adapter not yet wired (P2.5)")
    raise ValueError(f"unknown retriever {name!r}")
