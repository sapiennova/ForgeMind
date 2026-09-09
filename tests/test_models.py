"""Tests for ForgeMind SQLAlchemy domain models."""

from datetime import timezone
from uuid import UUID

from sqlalchemy import create_engine, inspect

from backend.app.models.base import Base
from backend.app.models.organization import Organization
from backend.app.models.plant import Plant


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


def test_plant_uses_shared_declarative_base():
    """Plant inherits from ForgeMind's shared SQLAlchemy base."""
    assert issubclass(Plant, Base)


def test_plant_maps_to_plants_table():
    """Plant is mapped to the expected database table."""
    assert Plant.__tablename__ == "plants"
    assert Plant.__table__.name == "plants"


def test_new_plant_receives_uuid_compatible_id():
    """Plant IDs are generated in application code as UUID values."""
    organization = Organization(name="Acme Manufacturing")
    plant = Plant(organization_id=organization.id, name="North Plant")

    assert isinstance(plant.id, UUID)


def test_new_plants_receive_distinct_ids():
    """Each Plant instance receives a unique identifier."""
    organization = Organization(name="Acme Manufacturing")
    first = Plant(organization_id=organization.id, name="North Plant")
    second = Plant(organization_id=organization.id, name="South Plant")

    assert first.id != second.id


def test_plant_stores_name():
    """Plant preserves its required name value."""
    organization = Organization(name="Acme Manufacturing")
    plant = Plant(organization_id=organization.id, name="North Plant")

    assert plant.name == "North Plant"


def test_new_plant_receives_timezone_aware_created_at():
    """Plant timestamps are created automatically in UTC."""
    organization = Organization(name="Acme Manufacturing")
    plant = Plant(organization_id=organization.id, name="North Plant")

    assert plant.created_at is not None
    assert plant.created_at.tzinfo is not None
    assert plant.created_at.utcoffset() == timezone.utc.utcoffset(plant.created_at)


def test_plant_has_foreign_key_to_organizations():
    """Plant ownership is stored as a foreign key to an organization."""
    foreign_keys = list(Plant.__table__.foreign_keys)

    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "organizations.id"
    assert Plant.__table__.c.organization_id.nullable is False


def test_organization_to_plant_relationship_works_in_both_directions():
    """Organizations expose plants and plants expose their owner."""
    organization = Organization(name="Acme Manufacturing")
    plant = Plant(organization_id=organization.id, name="North Plant")

    organization.plants.append(plant)

    assert organization.plants == [plant]
    assert plant.organization is organization


def test_organization_can_contain_multiple_plants():
    """One organization can be associated with multiple plants."""
    organization = Organization(name="Acme Manufacturing")
    first = Plant(organization_id=organization.id, name="North Plant")
    second = Plant(organization_id=organization.id, name="South Plant")

    organization.plants.extend([first, second])

    assert organization.plants == [first, second]
    assert first.organization is organization
    assert second.organization is organization


def test_organization_and_plant_tables_can_be_created_with_sqlite():
    """Organization and Plant schemas are compatible with SQLite."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    Base.metadata.create_all(engine)

    table_names = inspect(engine).get_table_names()
    assert "organizations" in table_names
    assert "plants" in table_names
