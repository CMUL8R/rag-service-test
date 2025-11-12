from typing import List

import structlog

from app.rag.vectorstore import vector_store

logger = structlog.get_logger()


class RagRetriever:
    def __init__(self, top_k: int = 3):
        self.top_k = top_k

    def retrieve(self, question: str) -> List[dict]:
        if not question.strip():
            return []
        docs = vector_store.similarity_search(question, k=self.top_k)
        logger.info("retriever_results", hits=len(docs))
        return docs

    @staticmethod
    def format_context(docs: List[dict]) -> str:
        parts = []
        for doc in docs:
            parts.append(
                f"Source: {doc['filename']}\n{doc['content']}"
            )
        return "\n\n".join(parts)


rag_retriever = RagRetriever()
