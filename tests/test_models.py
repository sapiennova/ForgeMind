"""Tests for ForgeMind SQLAlchemy domain models."""

from datetime import timezone
from uuid import UUID

from sqlalchemy import create_engine, inspect

from backend.app.models.base import Base
from backend.app.models.organization import Organization


def test_organization_inherits_from_shared_base():
    """Organization uses the shared ForgeMind declarative base."""
    assert issubclass(Organization, Base)


def test_organization_maps_to_organizations_table():
    """Organization maps to the expected table name."""
    assert Organization.__tablename__ == "organizations"


def test_organization_generates_id_name_and_creation_time():
    """New organizations receive an ID and UTC-aware creation timestamp."""
    organization = Organization(name="ForgeMind")

    assert isinstance(organization.id, UUID)
    assert organization.name == "ForgeMind"
    assert organization.created_at.tzinfo is timezone.utc


def test_new_organizations_receive_distinct_ids():
    """Application-generated organization IDs are unique per instance."""
    first = Organization(name="First")
    second = Organization(name="Second")

    assert first.id != second.id


def test_model_metadata_creates_organization_table_in_sqlite():
    """Organization metadata can create its table without PostgreSQL."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    Base.metadata.create_all(engine)

    assert "organizations" in inspect(engine).get_table_names()
