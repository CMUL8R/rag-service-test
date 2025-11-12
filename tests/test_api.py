import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.main import app
from app.rag.vectorstore import vector_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_vector_store():
    vector_store.clear()
    yield
    vector_store.clear()


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data
    assert "qdrant" in data


@patch('app.api.routes.llm_service')
@patch('app.api.routes.rag_retriever')
@patch('app.api.routes.cache_manager')
def test_ask_question_success(mock_cache, mock_retriever, mock_llm):
    """Test successful question answering"""
    # Mock cache miss
    mock_cache.get.return_value = None
    
    # Mock retriever
    mock_retriever.retrieve.return_value = [
        {
            "filename": "test.txt",
            "content": "Test content",
            "score": 0.95
        }
    ]
    mock_retriever.format_context.return_value = "Test context"
    
    # Mock LLM
    mock_llm.generate_answer.return_value = ("Test answer", 100)
    
    response = client.post(
        "/api/ask",
        json={"question": "What is test?"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "tokens_used" in data
    assert data["answer"] == "Test answer"
    assert data["tokens_used"] == 100


@patch('app.api.routes.rag_retriever')
def test_ask_question_no_documents(mock_retriever):
    """Test question when no documents found"""
    mock_retriever.retrieve.return_value = []
    
    response = client.post(
        "/api/ask",
        json={"question": "What is test?"}
    )
    
    assert response.status_code == 404


def test_ask_question_invalid_input():
    """Test question with invalid input"""
    response = client.post(
        "/api/ask",
        json={"question": ""}
    )
    
    assert response.status_code == 422


@patch('app.api.routes.cache_manager')
def test_ask_question_cache_hit(mock_cache):
    """Test question with cache hit"""
    cached_response = {
        "answer": "Cached answer",
        "sources": [
            {
                "document": "test.txt",
                "content": "Test content",
                "score": 0.95
            }
        ],
        "tokens_used": 50,
        "response_time": 0.5
    }
    mock_cache.get.return_value = cached_response
    
    response = client.post(
        "/api/ask",
        json={"question": "What is test?"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["cache_hit"] is True
    assert data["answer"] == "Cached answer"


def test_metrics_endpoint():
    """Test metrics endpoint"""
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_queries" in data
    assert "cache_hit_rate" in data
    assert "avg_response_time" in data
    assert "avg_tokens_used" in data


def _build_pdf(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)

    font_dict = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_dict})
        }
    )

    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 50 150 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_integration_question_flow():
    """Full pipeline: upload PDF via API -> ask question."""
    pdf_bytes = _build_pdf(
        "Start the service with docker compose up and wait until all components are healthy."
    )
    upload_response = client.post(
        "/api/documents",
        files={"file": ("guide.pdf", pdf_bytes, "application/pdf")}
    )
    assert upload_response.status_code == 200
    assert upload_response.json()["chunks"] > 0

    response = client.post(
        "/api/ask",
        json={"question": "Как запустить сервис?"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sources"], "ожидались источники"
    assert any("docker compose" in src["content"].lower() for src in data["sources"])
    assert "docker compose" in data["answer"].lower()
