from __future__ import annotations

import uuid
from typing import Dict, List

import structlog

from app.config import settings
from app.rag.embeddings import text_embedder

logger = structlog.get_logger()

try:  # optional dependency, only used when installed
    from qdrant_client import QdrantClient  # type: ignore
    from qdrant_client.http import models as qmodels  # type: ignore
except Exception:  # pragma: no cover
    QdrantClient = None  # type: ignore
    qmodels = None  # type: ignore


def _cosine_similarity(vector_a: List[float], vector_b: List[float]) -> float:
    return sum(a * b for a, b in zip(vector_a, vector_b))


class VectorStore:
    """Qdrant-based vector store with graceful in-memory fallback."""

    def __init__(self):
        self._memory_docs: List[Dict] = []
        self._client = None
        self._dimension = text_embedder.dimension
        self._collection = settings.qdrant_collection

        if QdrantClient:
            try:
                self._client = QdrantClient(
                    host=settings.qdrant_host,
                    port=settings.qdrant_port,
                    timeout=5,
                )
                self._ensure_collection()
                logger.info(
                    "qdrant_connected",
                    host=settings.qdrant_host,
                    port=settings.qdrant_port,
                    collection=self._collection,
                )
            except Exception as exc:  # pragma: no cover - depends on external service
                logger.warning("qdrant_connection_failed", error=str(exc))
                self._client = None

    def _ensure_collection(self):
        if not self._client:
            return
        exists = False
        try:
            exists = bool(self._client.collection_exists(self._collection))
        except AttributeError:  # older client
            try:
                self._client.get_collection(self._collection)
                exists = True
            except Exception:
                exists = False

        if not exists:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=qmodels.VectorParams(
                    size=self._dimension,
                    distance=qmodels.Distance.COSINE,
                ),
            )

    def add_documents(self, chunks: List[Dict]) -> int:
        valid_chunks = [
            chunk for chunk in chunks if chunk.get("content", "").strip()
        ]
        if not valid_chunks:
            return 0

        embeddings = text_embedder.embed([chunk["content"] for chunk in valid_chunks])

        if self._client:
            points = []
            for chunk, embedding in zip(valid_chunks, embeddings):
                points.append(
                    qmodels.PointStruct(
                        id=chunk.get("id") or str(uuid.uuid4()),
                        vector=embedding,
                        payload={
                            "filename": chunk.get("filename", "unknown"),
                            "content": chunk["content"],
                        },
                    )
                )
            try:
                self._client.upsert(
                    collection_name=self._collection,
                    points=points,
                    wait=True,
                )
                logger.info(
                    "vector_store_upsert",
                    backend="qdrant",
                    points=len(points),
                )
                self._store_in_memory(valid_chunks, embeddings, reason="qdrant_replica")
                return len(points)
            except Exception as exc:  # pragma: no cover
                logger.warning("qdrant_upsert_failed", error=str(exc))
                self._client = None  # fallback to memory

        self._store_in_memory(valid_chunks, embeddings)
        return len(valid_chunks)

    def _store_in_memory(
        self,
        chunks: List[Dict],
        embeddings: List[List[float]],
        reason: str = "memory_only",
    ):
        for chunk, embedding in zip(chunks, embeddings):
            self._memory_docs.append(
                {
                    "filename": chunk.get("filename", "unknown"),
                    "content": chunk["content"],
                    "embedding": embedding,
                }
            )
        logger.info(
            "vector_store_cache_update",
            backend="memory",
            points=len(chunks),
            reason=reason,
        )

    def similarity_search(self, query: str, k: int = 3) -> List[Dict]:
        if not query.strip():
            return []
        query_vector = text_embedder.embed_one(query)

        if self._client:
            try:
                hits = self._client.search(
                    collection_name=self._collection,
                    query_vector=query_vector,
                    limit=k,
                )
                return [
                    {
                        "filename": hit.payload.get("filename", "unknown"),
                        "content": hit.payload.get("content", ""),
                        "score": float(hit.score or 0.0),
                    }
                    for hit in hits
                ]
            except Exception as exc:  # pragma: no cover
                logger.warning("qdrant_search_failed", error=str(exc))
                self._client = None

        if not self._memory_docs:
            return []

        scored = []
        for doc in self._memory_docs:
            score = _cosine_similarity(query_vector, doc["embedding"])
            scored.append(
                {
                    "filename": doc["filename"],
                    "content": doc["content"],
                    "score": float(score),
                }
            )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:k]

    def health_check(self) -> bool:
        if self._client:
            try:
                self._client.get_collection(self._collection)
                return True
            except Exception:  # pragma: no cover
                return False
        return bool(self._memory_docs)

    def clear(self):
        self._memory_docs.clear()
        if self._client:
            try:
                self._client.delete_collection(self._collection)
                self._ensure_collection()
            except Exception as exc:  # pragma: no cover
                logger.warning("qdrant_clear_failed", error=str(exc))


vector_store = VectorStore()
