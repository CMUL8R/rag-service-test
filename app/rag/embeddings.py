from __future__ import annotations

import hashlib
import math
import re
from typing import List, Sequence

import structlog

from app.config import settings

logger = structlog.get_logger()

try:  # optional heavy dependency
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover
    SentenceTransformer = None  # type: ignore


class TextEmbedder:
    """Embeds text with SentenceTransformers when available, otherwise hash-based vectors."""

    def __init__(self):
        self.model_name = settings.embedding_model
        self._model = None
        self.dimension = 512  # fallback dimension

        if SentenceTransformer:
            try:
                self._model = SentenceTransformer(self.model_name)
                self.dimension = int(self._model.get_sentence_embedding_dimension())
                logger.info("embedder_loaded", model=self.model_name, dimension=self.dimension)
            except Exception as exc:  # pragma: no cover - depends on optional model download
                logger.warning("embedder_load_failed", error=str(exc))
                self._model = None

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        if self._model:
            embeddings = self._model.encode(
                list(texts),
                normalize_embeddings=True,
                convert_to_numpy=False
            )
            return [list(map(float, vector)) for vector in embeddings]
        return [self._hash_embed(text) for text in texts]

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]

    def _hash_embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vector
        for token in tokens:
            token_hash = int(hashlib.sha256(token.encode()).hexdigest(), 16)
            idx = token_hash % self.dimension
            vector[idx] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


text_embedder = TextEmbedder()
