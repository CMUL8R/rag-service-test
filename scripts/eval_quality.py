"""
Simple heuristic eval: runs predefined questions through the RAG pipeline
and reports keyword recall, tokens used, and latency.
"""

import json
import time

import structlog

from app.cache import cache_manager
from app.models import QuestionRequest
from app.rag.retriever import rag_retriever
from app.services.llm import llm_service

logger = structlog.get_logger()

EVAL_SET = [
    {
        "question": "Как запустить сервис через Docker Compose?",
        "keywords": ["docker", "compose", "up"],
    },
    {
        "question": "Как добавить новый документ в базу знаний?",
        "keywords": ["upload", "document"],
    },
    {
        "question": "Какие компоненты входят в архитектуру FAQ?",
        "keywords": ["fastapi", "redis", "postgres"],
    },
]


def run_eval():
    results = []
    for sample in EVAL_SET:
        question = QuestionRequest(question=sample["question"])
        start = time.time()
        docs = rag_retriever.retrieve(question.question)
        context = rag_retriever.format_context(docs)
        answer, tokens = llm_service.generate_answer(question.question, context)
        elapsed = time.time() - start

        success = all(keyword.lower() in answer.lower() for keyword in sample["keywords"])
        results.append(
            {
                "question": question.question,
                "tokens": tokens,
                "latency": elapsed,
                "success": success,
                "sources": [doc["filename"] for doc in docs],
            }
        )
        logger.info(
            "eval_sample",
            question=question.question,
            success=success,
            latency=elapsed,
            tokens=tokens,
        )

    cache_manager.health_check()  # warm redis ping for metrics
    report = {
        "samples": results,
        "success_rate": sum(1 for item in results if item["success"]) / len(results),
        "avg_tokens": sum(item["tokens"] for item in results) / len(results),
        "avg_latency": sum(item["latency"] for item in results) / len(results),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run_eval()
