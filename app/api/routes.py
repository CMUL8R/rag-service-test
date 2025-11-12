import io
import json
import time

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pypdf import PdfReader
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models import (
    QuestionRequest, QuestionResponse, Source,
    HealthResponse, MetricsResponse, QueryHistory
)
from app.database import get_db_dependency
from app.cache import cache_manager
from app.rag.retriever import rag_retriever
from app.rag.vectorstore import vector_store
from app.services.llm import llm_service
from app.services.document import document_processor

logger = structlog.get_logger()
router = APIRouter()


@router.post("/api/ask", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    db: Session = Depends(get_db_dependency)
):
    """Answer a question using RAG"""
    start_time = time.time()
    
    try:
        # Check cache
        cached = cache_manager.get(request.question)
        if cached:
            response = QuestionResponse(**cached, cache_hit=True)
            
            # Log cache hit
            history = QueryHistory(
                question=request.question,
                answer=response.answer,
                tokens_used=response.tokens_used,
                response_time=response.response_time,
                sources=json.dumps([s.model_dump() for s in response.sources]),
                cache_hit=1
            )
            db.add(history)
            db.commit()
            
            return response
        
        # Retrieve relevant documents
        retrieved_docs = rag_retriever.retrieve(request.question)
        
        if not retrieved_docs:
            raise HTTPException(
                status_code=404,
                detail="No relevant documents found in knowledge base"
            )
        
        # Format context
        context = rag_retriever.format_context(retrieved_docs)
        
        # Generate answer
        answer, tokens = llm_service.generate_answer(request.question, context)
        
        response_time = time.time() - start_time
        
        # Prepare sources
        sources = [
            Source(
                document=doc["filename"],
                content=doc["content"][:200] + "...",
                score=doc["score"]
            )
            for doc in retrieved_docs
        ]
        
        response = QuestionResponse(
            answer=answer,
            sources=sources,
            tokens_used=tokens,
            response_time=response_time,
            cache_hit=False
        )
        
        # Cache response
        cache_manager.set(
            request.question,
            response.model_dump(exclude={"cache_hit"})
        )
        
        # Save to database
        history = QueryHistory(
            question=request.question,
            answer=answer,
            tokens_used=tokens,
            response_time=response_time,
            sources=json.dumps([s.model_dump() for s in sources]),
            cache_hit=0
        )
        db.add(history)
        db.commit()
        
        logger.info(
            "question_answered",
            tokens=tokens,
            response_time=response_time,
            cache_hit=False
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("question_processing_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf")


def _extract_pdf_text(raw_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        text_content = "\n".join(part.strip() for part in pages if part).strip()
        if not text_content:
            raise ValueError("empty pdf")
        return text_content
    except Exception as exc:  # pragma: no cover - depends on third party PDF contents
        logger.error("pdf_parse_failed", error=str(exc))
        raise HTTPException(status_code=400, detail="Не удалось распарсить PDF") from exc


def _read_file_contents(filename: str, raw_bytes: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        return _extract_pdf_text(raw_bytes)
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Неподдерживаемая кодировка файла") from exc


@router.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a document"""
    try:
        if not file.filename.lower().endswith(SUPPORTED_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail="Поддерживаются только .txt, .md и .pdf"
            )
        
        raw_bytes = await file.read()
        content = _read_file_contents(file.filename, raw_bytes)
        
        # Process document
        chunks = document_processor.process_document(file.filename, content)
        
        # Add to vector store
        vector_store.add_documents(chunks)
        
        logger.info("document_uploaded", filename=file.filename, chunks=len(chunks))
        
        return {
            "message": "Document uploaded successfully",
            "filename": file.filename,
            "chunks": len(chunks)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("document_upload_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/api/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db_dependency)):
    """Health check endpoint"""
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    # Check Redis
    redis_status = "healthy" if cache_manager.health_check() else "unhealthy"
    
    # Check Qdrant
    qdrant_status = "healthy" if vector_store.health_check() else "unhealthy"
    
    overall_status = "healthy" if all(
        s == "healthy" for s in [db_status, redis_status, qdrant_status]
    ) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        database=db_status,
        redis=redis_status,
        qdrant=qdrant_status
    )


@router.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics(db: Session = Depends(get_db_dependency)):
    """Get service metrics"""
    try:
        total_queries = db.query(func.count(QueryHistory.id)).scalar() or 0
        
        if total_queries == 0:
            return MetricsResponse(
                total_queries=0,
                cache_hit_rate=0.0,
                avg_response_time=0.0,
                avg_tokens_used=0.0
            )
        
        cache_hits = db.query(func.sum(QueryHistory.cache_hit)).scalar() or 0
        avg_time = db.query(func.avg(QueryHistory.response_time)).scalar() or 0.0
        avg_tokens = db.query(func.avg(QueryHistory.tokens_used)).scalar() or 0.0
        
        return MetricsResponse(
            total_queries=total_queries,
            cache_hit_rate=cache_hits / total_queries,
            avg_response_time=float(avg_time),
            avg_tokens_used=float(avg_tokens)
        )
        
    except Exception as e:
        logger.error("metrics_retrieval_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")
