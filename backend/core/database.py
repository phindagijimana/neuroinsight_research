"""
Database Management Module

Provides SQLAlchemy database engine, session management, and utilities.
Supports both PostgreSQL (production) and SQLite (fallback/testing).

ARCHITECTURE:
- Engine: Single database connection pool (singleton)
- SessionLocal: Factory for creating database sessions
- Dependency Injection: get_db() for FastAPI route dependencies
- Context Manager: get_db_context() for standalone database access (Celery tasks)
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, Engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.core.config import get_settings
from backend.models.job import Base

logger = logging.getLogger(__name__)

settings = get_settings()


def get_engine_config(database_url: str, environment: str) -> dict:
    """Get database engine configuration based on database type and environment."""
    config = {
        "echo": (environment == "development"),
        "pool_pre_ping": True,
    }

    if database_url.startswith("sqlite"):
        config.update({
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        })
    else:
        # PostgreSQL / MySQL
        config.update({
            "pool_size": 10,
            "max_overflow": 20,
            "pool_recycle": 3600,
        })

    return config


# Create SQLAlchemy engine (singleton)
engine: Engine = create_engine(
    settings.database_url,
    **get_engine_config(settings.database_url, settings.environment)
)


# SQLite-only pragma (no-op for PostgreSQL)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable SQLite foreign key constraints and optimizations (SQLite only)."""
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def init_db() -> None:
    """Initialize database schema (idempotent)."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info(f"Database initialized: {settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def drop_db() -> None:
    """Drop all tables. WARNING: destroys all data."""
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency -- yields a session, auto-closes on request end."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error in request: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for background tasks and Celery workers."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def health_check() -> dict:
    """Check database connectivity."""
    try:
        with get_db_context() as db:
            db.execute(text("SELECT 1"))

        db_info = settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url
        return {
            "healthy": True,
            "message": "Database connection OK",
            "database": db_info,
        }
    except Exception as e:
        return {
            "healthy": False,
            "message": f"Database connection failed: {str(e)}",
        }
