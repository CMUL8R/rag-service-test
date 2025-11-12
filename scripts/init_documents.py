"""
CLI helper to ingest all .txt/.md files from ./documents into the vector store.

Usage:
    python scripts/init_documents.py
"""

from pathlib import Path

import structlog

from app.rag.vectorstore import vector_store
from app.services.document import document_processor

logger = structlog.get_logger()


def ingest_documents(directory: Path) -> int:
    total_chunks = 0
    files = 0

    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".md"}:
            continue
        files += 1
        content = path.read_text(encoding="utf-8")
        chunks = document_processor.process_document(path.name, content)
        vector_store.add_documents(chunks)
        total_chunks += len(chunks)
        logger.info("document_indexed", file=path.name, chunks=len(chunks))
    return files, total_chunks


def main():
    documents_path = Path("documents")
    if not documents_path.exists():
        logger.warning("documents_dir_missing", path=str(documents_path.resolve()))
        return
    files, chunks = ingest_documents(documents_path)
    logger.info("documents_ingestion_completed", files=files, chunks=chunks)
    print(f"Indexed {chunks} chunks from {files} files.")


if __name__ == "__main__":
    main()
