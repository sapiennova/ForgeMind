"""Database infrastructure shared by future ForgeMind API endpoints."""

import os
from collections.abc import Generator
from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

_DATABASE_URL_ENV = "DATABASE_URL"

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker[Session]] = None


def get_database_url() -> str:
    """Return the configured database URL or fail with a clear error."""
    database_url = os.getenv(_DATABASE_URL_ENV)
    if not database_url:
        raise RuntimeError(f"{_DATABASE_URL_ENV} environment variable must be set.")
    return database_url


def get_engine() -> Engine:
    """Lazily create and cache the SQLAlchemy engine."""
    global _engine

    if _engine is None:
        _engine = create_engine(get_database_url(), pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the session factory bound to the shared engine."""
    global _session_factory

    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False)
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for use as a FastAPI dependency."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
