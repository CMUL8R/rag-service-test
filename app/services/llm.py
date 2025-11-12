from __future__ import annotations

import textwrap
from typing import Tuple

import structlog

from app.config import settings

try:  # Optional dependency, not required for tests
    import anthropic  # type: ignore
except Exception:  # pragma: no cover
    anthropic = None

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None

logger = structlog.get_logger()


class LLMService:
    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self.max_tokens = settings.max_tokens
        self.temperature = settings.temperature

        self._anthropic_client = None
        self._openai_client = None

        if anthropic and settings.anthropic_api_key:
            self._anthropic_client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key
            )
        if OpenAI and settings.openai_api_key:
            self._openai_client = OpenAI(api_key=settings.openai_api_key)

    def generate_answer(self, question: str, context: str) -> Tuple[str, int]:
        if self.provider == "anthropic" and self._anthropic_client:
            try:
                response = self._anthropic_client.messages.create(
                    model="claude-2.1",
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=[
                        {
                            "role": "user",
                            "content": f"Answer the question based on the context.\nContext:{context}\nQuestion:{question}",
                        }
                    ],
                )
                answer = response.content[0].text  # type: ignore[index]
                return answer, self._count_tokens(answer)
            except Exception as exc:  # pragma: no cover - network path
                logger.warning("anthropic_call_failed", error=str(exc))

        if self.provider == "openai" and self._openai_client:
            try:
                completion = self._openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that answers questions using the provided context only.",
                        },
                        {
                            "role": "user",
                            "content": f"Context:\n{context}\n\nQuestion: {question}",
                        },
                    ],
                )
                answer = completion.choices[0].message.content  # type: ignore[index]
                return answer, self._count_tokens(answer)
            except Exception as exc:  # pragma: no cover
                logger.warning("openai_call_failed", error=str(exc))

        # Fallback deterministic answer for local/dev & tests
        answer = self._fallback_answer(question, context)
        return answer, self._count_tokens(answer)

    @staticmethod
    def _count_tokens(text: str) -> int:
        return max(1, len(text.split()))

    def _fallback_answer(self, question: str, context: str) -> str:
        if not context.strip():
            return "I could not find relevant information in the knowledge base."

        snippet = textwrap.shorten(context.replace("\n", " "), width=600, placeholder="...")
        return (
            "This is an offline answer generated without calling an external LLM. "
            "Based on the available context, here is the most relevant information: "
            f"{snippet}"
            "\n\nQuestion answered: "
            f"{question.strip()}"
        )


default_llm_service = LLMService()
llm_service = default_llm_service
