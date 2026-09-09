"""Tests for ForgeMind SQLAlchemy domain models."""

from datetime import timezone
from uuid import UUID

from sqlalchemy import create_engine, inspect

from backend.app.models.base import Base
from backend.app.models.organization import Organization


def test_organization_uses_shared_declarative_base():
    """Organization inherits from ForgeMind's shared SQLAlchemy base."""
    assert issubclass(Organization, Base)


def test_organization_maps_to_organizations_table():
    """Organization is mapped to the expected database table."""
    assert Organization.__tablename__ == "organizations"
    assert Organization.__table__.name == "organizations"


def test_new_organization_receives_uuid_compatible_id():
    """Organization IDs are generated in application code as UUID values."""
    organization = Organization(name="Acme Manufacturing")

    assert isinstance(organization.id, UUID)


def test_new_organizations_receive_distinct_ids():
    """Each Organization instance receives a unique identifier."""
    first = Organization(name="Acme Manufacturing")
    second = Organization(name="Beta Industries")

    assert first.id != second.id


def test_organization_stores_name():
    """Organization preserves its required name value."""
    organization = Organization(name="Acme Manufacturing")

    assert organization.name == "Acme Manufacturing"


def test_new_organization_receives_timezone_aware_created_at():
    """Organization timestamps are created automatically in UTC."""
    organization = Organization(name="Acme Manufacturing")

    assert organization.created_at is not None
    assert organization.created_at.tzinfo is not None
    assert organization.created_at.utcoffset() == timezone.utc.utcoffset(organization.created_at)


def test_organization_table_can_be_created_with_sqlite():
    """Organization schema is compatible with SQLite for isolated tests."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    Base.metadata.create_all(engine)

    assert "organizations" in inspect(engine).get_table_names()
