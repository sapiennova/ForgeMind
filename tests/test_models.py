"""Tests for ForgeMind SQLAlchemy domain models."""

from datetime import timezone
from uuid import UUID

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.base import Base
from backend.app.models.machine import Machine
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

    try:
        Base.metadata.create_all(engine)

        assert "organizations" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


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


def test_all_domain_tables_can_be_created_with_sqlite():
    """The complete domain hierarchy is compatible with SQLite."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    try:
        Base.metadata.create_all(engine)

        table_names = inspect(engine).get_table_names()
        assert "organizations" in table_names
        assert "plants" in table_names
        assert "production_lines" in table_names
        assert "machines" in table_names
    finally:
        engine.dispose()


def _production_line() -> ProductionLine:
    """Create a production line for Machine model tests."""
    organization = Organization(name="Acme Manufacturing")
    plant = Plant(organization_id=organization.id, name="North Plant")
    return ProductionLine(plant_id=plant.id, name="Assembly Line 1")


def test_machine_uses_shared_declarative_base():
    """Machine inherits from ForgeMind's shared SQLAlchemy base."""
    assert issubclass(Machine, Base)


def test_machine_maps_to_machines_table():
    """Machine is mapped to the expected database table."""
    assert Machine.__tablename__ == "machines"
    assert Machine.__table__.name == "machines"


def test_new_machine_receives_uuid_compatible_id():
    """Machine IDs are generated in application code as UUID values."""
    production_line = _production_line()
    machine = Machine(production_line.id, "CNC-001", "CNC Mill 1", "CNC")

    assert isinstance(machine.id, UUID)


def test_new_machines_receive_distinct_ids():
    """Each Machine instance receives a unique identifier."""
    production_line = _production_line()
    first = Machine(production_line.id, "CNC-001", "CNC Mill 1", "CNC")
    second = Machine(production_line.id, "PRESS-042", "Press 42", "PRESS")

    assert first.id != second.id


def test_machine_stores_name_asset_id_and_machine_type():
    """Machine preserves its required identity and classification values."""
    machine = Machine(_production_line().id, "ROBOT-17", "Welding Robot", "ROBOT")

    assert machine.name == "Welding Robot"
    assert machine.asset_id == "ROBOT-17"
    assert machine.machine_type == "ROBOT"


def test_machine_asset_id_is_unique_in_sqlite():
    """The database rejects duplicate stable industrial asset identifiers."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    try:
        Base.metadata.create_all(engine)
        organization = Organization(name="Acme Manufacturing")
        plant = Plant(organization_id=organization.id, name="North Plant")
        production_line = ProductionLine(plant_id=plant.id, name="Assembly Line 1")
        with Session(engine) as session:
            session.add_all([organization, plant, production_line])
            session.add(Machine(production_line.id, "CNC-001", "CNC Mill 1", "CNC"))
            session.commit()

            session.add(Machine(production_line.id, "CNC-001", "CNC Mill 2", "CNC"))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
            else:
                raise AssertionError("SQLite accepted duplicate machine asset_id values")
    finally:
        engine.dispose()


def test_new_machine_defaults_to_active_with_timezone_aware_created_at():
    """Machines default to active and receive automatic UTC timestamps."""
    machine = Machine(_production_line().id, "CONVEYOR-01", "Main Conveyor", "CONVEYOR")

    assert machine.status == "active"
    assert machine.created_at is not None
    assert machine.created_at.tzinfo is not None
    assert machine.created_at.utcoffset() == timezone.utc.utcoffset(machine.created_at)


def test_machine_has_non_null_foreign_key_to_production_lines():
    """Machine ownership is stored as a required production line foreign key."""
    foreign_keys = list(Machine.__table__.foreign_keys)

    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "production_lines.id"
    assert Machine.__table__.c.production_line_id.nullable is False


def test_production_line_to_machine_relationship_works_in_both_directions():
    """Production lines expose machines and machines expose their owner."""
    production_line = _production_line()
    machine = Machine(production_line.id, "CNC-001", "CNC Mill 1", "CNC")

    production_line.machines.append(machine)

    assert production_line.machines == [machine]
    assert machine.production_line is production_line


def test_production_line_can_contain_multiple_machines():
    """One production line can be associated with multiple machines."""
    production_line = _production_line()
    first = Machine(production_line.id, "CNC-001", "CNC Mill 1", "CNC")
    second = Machine(production_line.id, "PRESS-042", "Press 42", "PRESS")

    production_line.machines.extend([first, second])

    assert production_line.machines == [first, second]
    assert first.production_line is production_line
    assert second.production_line is production_line
