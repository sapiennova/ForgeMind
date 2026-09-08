"""Database engine and session configuration."""

import os
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def get_database_url() -> str:
    """Return the database URL configured for the application."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable must be set.")
    return database_url


@lru_cache
def get_engine() -> Engine:
    """Create the SQLAlchemy engine when database access is first needed."""
    return create_engine(get_database_url(), pool_pre_ping=True)


SessionLocal = sessionmaker(autoflush=False, autocommit=False)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for use as a FastAPI dependency."""
    session = SessionLocal(bind=get_engine())
    try:
        yield session
    finally:
        session.close()
