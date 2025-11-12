from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field, constr
from sqlalchemy import Column, DateTime, Float, Integer, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    tokens_used = Column(Integer, nullable=False, default=0)
    response_time = Column(Float, nullable=False, default=0.0)
    sources = Column(Text, nullable=False, default="[]")
    cache_hit = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class QuestionRequest(BaseModel):
    question: constr(strip_whitespace=True, min_length=1)


class Source(BaseModel):
    document: str
    content: str
    score: float


class QuestionResponse(BaseModel):
    answer: str
    sources: List[Source] = Field(default_factory=list)
    tokens_used: int = 0
    response_time: float = 0.0
    cache_hit: bool = False


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    qdrant: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsResponse(BaseModel):
    total_queries: int
    cache_hit_rate: float
    avg_response_time: float
    avg_tokens_used: float
