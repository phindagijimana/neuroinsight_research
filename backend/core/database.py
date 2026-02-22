"""
Database configuration and session management.

This module provides SQLAlchemy database connection handling,
session management, and base model class.
"""

from typing import Generator

import sqlalchemy.pool
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .logging import get_logger

# Get application settings
settings = get_settings()

# Get logger for database operations
logger = get_logger(__name__)

# Create SQLAlchemy engine with database-specific optimizations
connect_args = {}
pool_class = None
pool_kwargs = {}

if settings.database_url.startswith("sqlite"):
    # SQLite-specific settings for web deployment
    connect_args = {"check_same_thread": False, "isolation_level": None}
    pool_class = sqlalchemy.pool.NullPool

elif "postgresql" in settings.database_url:
    # PostgreSQL-specific settings for production deployment
    connect_args = {"application_name": "neuroinsight"}
    pool_class = sqlalchemy.pool.QueuePool

    # PostgreSQL connection pool settings
    pool_kwargs = {
        "pool_size": 10,          # Base pool size
        "max_overflow": 20,       # Additional connections allowed
        "pool_timeout": 30,       # Connection timeout
        "pool_recycle": 3600,     # Recycle connections after 1 hour
        "pool_pre_ping": True,    # Test connections before use
    }

engine = create_engine(
    settings.database_url,
    poolclass=pool_class,
    echo=settings.environment == "development",
    connect_args=connect_args,
    **pool_kwargs
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency for FastAPI.
    
    Yields a database session and ensures it's closed after the request.
    Use this as a dependency in FastAPI route handlers.
    
    Example:
        @app.get("/jobs")
        def get_jobs(db: Session = Depends(get_db)):
            return db.query(Job).all()
    
    Yields:
        Session: SQLAlchemy database session
    """
    try:
        db = SessionLocal()
        yield db
    finally:
        if db:
            try:
                db.close()
            except:
                pass


def init_db() -> None:
    """
    Initialize database by creating all tables.
    
    This function creates all tables defined by models inheriting from Base.
    Should be called on application startup.
    
    Note:
        In production, use Alembic migrations instead of this function.
    """
    from backend.models import Job, Metric  # noqa: F401
    
    Base.metadata.create_all(bind=engine)

