"""RAG retrieval layer.

Chunks the markdown knowledge base by section headers and retrieves with
TF-IDF cosine similarity. The `Retriever` interface is backend-agnostic:
swap `TfidfBackend` for a dense-embedding backend (e.g. Voyage, BGE served
via vLLM) without touching the agent layer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import KB_DIR, MIN_SCORE, TOP_K


@dataclass
class Chunk:
    doc: str          # source filename
    title: str        # document H1
    section: str      # section H2
    text: str
    score: float = field(default=0.0)

    @property
    def citation(self) -> str:
        return f"{self.title} › {self.section}"


def load_chunks(kb_dir: Path = KB_DIR) -> list[Chunk]:
    """Split each markdown doc into one chunk per `##` section."""
    chunks: list[Chunk] = []
    for path in sorted(kb_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title_m = re.search(r"^# (.+)$", text, re.M)
        title = title_m.group(1).strip() if title_m else path.stem
        sections = re.split(r"^## ", text, flags=re.M)[1:]
        for sec in sections:
            header, _, body = sec.partition("\n")
            body = body.strip()
            if body:
                chunks.append(Chunk(doc=path.name, title=title,
                                    section=header.strip(), text=body))
    return chunks


class TfidfBackend:
    """Sparse lexical backend — zero external services, deploys anywhere."""

    def __init__(self, corpus: list[str]):
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), sublinear_tf=True, stop_words="english"
        )
        self.matrix = self.vectorizer.fit_transform(corpus)

    def scores(self, query: str) -> np.ndarray:
        q = self.vectorizer.transform([query])
        return cosine_similarity(q, self.matrix).ravel()


class Retriever:
    def __init__(self, kb_dir: Path = KB_DIR):
        self.chunks = load_chunks(kb_dir)
        texts = [f"{c.title} {c.section}\n{c.text}" for c in self.chunks]
        self.backend = TfidfBackend(texts)

    def search(self, query: str, top_k: int = TOP_K) -> list[Chunk]:
        scores = self.backend.scores(query)
        order = np.argsort(scores)[::-1][:top_k]
        results = []
        for i in order:
            if scores[i] < MIN_SCORE:
                continue
            c = self.chunks[int(i)]
            results.append(Chunk(c.doc, c.title, c.section, c.text,
                                 float(scores[i])))
        return results

    def format_context(self, chunks: list[Chunk]) -> str:
        """Render retrieved chunks as numbered context for the prompt."""
        if not chunks:
            return "NO_RELEVANT_DOCUMENTS_FOUND"
        parts = []
        for i, c in enumerate(chunks, 1):
            parts.append(
                f'<doc id="{i}" source="{c.citation}" score="{c.score:.2f}">\n'
                f"{c.text}\n</doc>"
            )
        return "\n".join(parts)
