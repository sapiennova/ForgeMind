"""Tests for ForgeMind SQLAlchemy domain models."""

from datetime import timezone
from uuid import UUID

from sqlalchemy import create_engine, inspect

from backend.app.models.base import Base
from backend.app.models.organization import Organization
from backend.app.models.plant import Plant
from backend.app.models.production_line import ProductionLine


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


def test_production_line_uses_shared_declarative_base():
    """ProductionLine inherits from ForgeMind's shared SQLAlchemy base."""
    assert issubclass(ProductionLine, Base)


def test_production_line_maps_to_production_lines_table():
    """ProductionLine is mapped to the expected database table."""
    assert ProductionLine.__tablename__ == "production_lines"
    assert ProductionLine.__table__.name == "production_lines"


def test_new_production_line_receives_uuid_compatible_id():
    """Production line IDs are generated in application code as UUID values."""
    plant = Plant(organization_id=Organization(name="Acme Manufacturing").id, name="North Plant")
    production_line = ProductionLine(plant_id=plant.id, name="Assembly Line 1")

    assert isinstance(production_line.id, UUID)


def test_new_production_lines_receive_distinct_ids():
    """Each ProductionLine instance receives a unique identifier."""
    plant = Plant(organization_id=Organization(name="Acme Manufacturing").id, name="North Plant")
    first = ProductionLine(plant_id=plant.id, name="Assembly Line 1")
    second = ProductionLine(plant_id=plant.id, name="Assembly Line 2")

    assert first.id != second.id


def test_production_line_stores_name():
    """ProductionLine preserves its required name value."""
    plant = Plant(organization_id=Organization(name="Acme Manufacturing").id, name="North Plant")
    production_line = ProductionLine(plant_id=plant.id, name="Assembly Line 1")

    assert production_line.name == "Assembly Line 1"


def test_new_production_line_receives_timezone_aware_created_at():
    """Production line timestamps are created automatically in UTC."""
    plant = Plant(organization_id=Organization(name="Acme Manufacturing").id, name="North Plant")
    production_line = ProductionLine(plant_id=plant.id, name="Assembly Line 1")

    assert production_line.created_at is not None
    assert production_line.created_at.tzinfo is not None
    assert production_line.created_at.utcoffset() == timezone.utc.utcoffset(production_line.created_at)


def test_production_line_has_foreign_key_to_plants():
    """Production line ownership is stored as a foreign key to a plant."""
    foreign_keys = list(ProductionLine.__table__.foreign_keys)

    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "plants.id"
    assert ProductionLine.__table__.c.plant_id.nullable is False


def test_plant_to_production_line_relationship_works_in_both_directions():
    """Plants expose production lines and production lines expose their owner."""
    plant = Plant(organization_id=Organization(name="Acme Manufacturing").id, name="North Plant")
    production_line = ProductionLine(plant_id=plant.id, name="Assembly Line 1")

    plant.production_lines.append(production_line)

    assert plant.production_lines == [production_line]
    assert production_line.plant is plant


def test_plant_can_contain_multiple_production_lines():
    """One plant can be associated with multiple production lines."""
    plant = Plant(organization_id=Organization(name="Acme Manufacturing").id, name="North Plant")
    first = ProductionLine(plant_id=plant.id, name="Assembly Line 1")
    second = ProductionLine(plant_id=plant.id, name="Assembly Line 2")

    plant.production_lines.extend([first, second])

    assert plant.production_lines == [first, second]
    assert first.plant is plant
    assert second.plant is plant


def test_organization_plant_and_production_line_tables_can_be_created_with_sqlite():
    """Organization, Plant, and ProductionLine schemas are compatible with SQLite."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    Base.metadata.create_all(engine)

    table_names = inspect(engine).get_table_names()
    assert "organizations" in table_names
    assert "plants" in table_names
    assert "production_lines" in table_names
