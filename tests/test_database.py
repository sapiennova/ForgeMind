"""Tests for the database infrastructure."""

import importlib

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import backend.app.database as database


@pytest.fixture
def database_module(monkeypatch):
    """Reload the database module so each test has an isolated engine cache."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return importlib.reload(database)


def test_database_url_is_read_from_environment(database_module, monkeypatch):
    """The database URL is sourced from DATABASE_URL."""
    database_url = "sqlite+pysqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", database_url)

    assert database_module.get_database_url() == database_url


def test_missing_database_url_raises_explicit_error(database_module):
    """Missing configuration should never fall back to a default database."""
    with pytest.raises(RuntimeError, match="DATABASE_URL environment variable must be set"):
        database_module.get_engine()


def test_engine_uses_configured_url_and_is_reused(database_module, monkeypatch):
    """The configured URL creates one shared engine without connecting to PostgreSQL."""
    database_url = "sqlite+pysqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", database_url)

    engine = database_module.get_engine()

    try:
        assert str(engine.url) == database_url
        assert database_module.get_engine() is engine
    finally:
        engine.dispose()


def test_session_dependency_yields_sqlalchemy_session(database_module, monkeypatch):
    """The FastAPI dependency yields and closes a SQLAlchemy Session."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    dependency = database_module.get_db()
    session = next(dependency)

    assert isinstance(session, Session)
    assert isinstance(database_module.get_engine(), Engine)

    dependency.close()
    database_module.get_engine().dispose()
