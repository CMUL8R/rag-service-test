from contextlib import contextmanager
from typing import Generator

import structlog
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base

logger = structlog.get_logger()


def _build_engine():
    """Create SQLAlchemy engine with sensible defaults."""
    url = settings.database_url
    connect_args = {}
    kwargs = {"pool_pre_ping": True}

    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        kwargs.clear()  # SQLite does not play well with pooling by default

    return create_engine(url, connect_args=connect_args, **kwargs)


engine = _build_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("database_initialized")
    except SQLAlchemyError as e:
        logger.error("database_init_failed", error=str(e))
        raise


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Database session context manager"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error("database_error", error=str(e))
        raise
    finally:
        db.close()


def get_db_dependency() -> Generator[Session, None, None]:
    """FastAPI dependency for database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Ensure tables exist in contexts (e.g., unit tests) that skip FastAPI lifespan.
try:
    init_db()
except Exception as exc:  # pragma: no cover - init errors logged above
    logger.warning("database_init_on_import_failed", error=str(exc))
