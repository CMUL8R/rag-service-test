from __future__ import annotations

from typing import Dict, List

from app.config import settings


def _chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    size = max(1, chunk_size)
    ov = max(0, min(overlap, size - 1))

    chunks = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(normalized):
            break
        start = end - ov
    return chunks


class DocumentProcessor:
    def process_document(self, filename: str, content: str) -> List[Dict]:
        """Split raw document into overlapping chunks ready for indexing."""
        chunks = _chunk_text(content, settings.chunk_size, settings.chunk_overlap)
        documents = []
        for idx, chunk in enumerate(chunks):
            documents.append(
                {
                    "id": f"{filename}:{idx}",
                    "filename": filename,
                    "content": chunk,
                }
            )
        return documents


document_processor = DocumentProcessor()
