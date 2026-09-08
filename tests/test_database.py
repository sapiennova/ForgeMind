"""Tests for database configuration."""

import pytest
from sqlalchemy.orm import Session

from backend.app import database


def test_get_database_url_reads_environment(monkeypatch):
    """Test that the database URL is read from environment configuration."""
    database_url = "sqlite+pysqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", database_url)

    assert database.get_database_url() == database_url


def test_get_database_url_requires_environment(monkeypatch):
    """Test that database configuration does not supply credentials."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        database.get_database_url()


def test_get_engine_uses_configured_url_without_connecting(monkeypatch):
    """Test engine creation without requiring an external database server."""
    database.get_engine.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    engine = database.get_engine()

    assert str(engine.url) == "sqlite+pysqlite:///:memory:"
    engine.dispose()
    database.get_engine.cache_clear()


def test_get_session_yields_sqlalchemy_session(monkeypatch):
    """Test the session dependency without requiring an external database."""
    database.get_engine.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    session_dependency = database.get_session()
    session = next(session_dependency)

    assert isinstance(session, Session)
    session_dependency.close()
    database.get_engine().dispose()
    database.get_engine.cache_clear()
