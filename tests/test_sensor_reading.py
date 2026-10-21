"""Tests for individual sensor telemetry readings."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from backend.app.models import SensorReading
from backend.app.models.base import Base
from backend.app.models.machine import Machine
from backend.app.models.organization import Organization
from backend.app.models.plant import Plant
from backend.app.models.production_line import ProductionLine
from backend.app.models.sensor import Sensor


def _sensor() -> Sensor:
    """Build an unsaved sensor with its required parent IDs."""
    organization = Organization(name="Acme Manufacturing")
    plant = Plant(organization_id=organization.id, name="North Plant")
    line = ProductionLine(plant_id=plant.id, name="Assembly Line 1")
    machine = Machine(line.id, "CNC-001", "CNC Mill", "CNC")
    return Sensor(machine.id, "TEMP-001", "Bearing Temperature", "temperature", "°C")


def test_sensor_reading_uses_shared_base_and_expected_table():
    """SensorReading uses the shared declarative base and table mapping."""
    assert issubclass(SensorReading, Base)
    assert SensorReading.__tablename__ == "sensor_readings"
    assert SensorReading.__table__.name == "sensor_readings"


def test_sensor_reading_ids_are_application_generated_and_distinct():
    """Each reading receives a distinct UUID at object creation."""
    sensor_id = _sensor().id
    first = SensorReading(sensor_id=sensor_id, value=21.5)
    second = SensorReading(sensor_id=sensor_id, value=22.0)

    assert isinstance(first.id, UUID)
    assert isinstance(second.id, UUID)
    assert first.id != second.id


def test_sensor_reading_stores_value_and_explicit_timestamp():
    """A reading preserves its measurement and supplied timestamp."""
    timestamp = datetime(2026, 10, 21, 10, 30, tzinfo=timezone.utc)
    reading = SensorReading(sensor_id=_sensor().id, value=23.75, recorded_at=timestamp)

    assert reading.value == 23.75
    assert reading.recorded_at == timestamp
    assert reading.recorded_at.utcoffset() == timezone.utc.utcoffset(timestamp)


def test_sensor_reading_defaults_to_timezone_aware_utc_timestamp():
    """Omitted recorded_at is initialized to a timezone-aware UTC time."""
    reading = SensorReading(sensor_id=_sensor().id, value=19.2)

    assert reading.recorded_at is not None
    assert reading.recorded_at.tzinfo is not None
    assert reading.recorded_at.utcoffset() == timezone.utc.utcoffset(reading.recorded_at)


def test_sensor_reading_has_required_sensor_foreign_key():
    """Every reading requires a foreign key to sensors.id."""
    foreign_keys = list(SensorReading.__table__.foreign_keys)

    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "sensors.id"
    assert SensorReading.__table__.c.sensor_id.nullable is False


def test_sensor_reading_value_and_timestamp_are_non_nullable():
    """Measurement value and recorded timestamp have database NOT NULL constraints."""
    columns = SensorReading.__table__.c

    assert columns.id.nullable is False
    assert columns.sensor_id.nullable is False
    assert columns.value.nullable is False
    assert columns.recorded_at.nullable is False


def test_sensor_and_readings_relationship_is_bidirectional_and_one_to_many():
    """A sensor exposes multiple readings and each reading points back to it."""
    sensor = _sensor()
    first = SensorReading(sensor_id=sensor.id, value=20.0)
    second = SensorReading(sensor_id=sensor.id, value=21.0)

    sensor.readings.extend([first, second])

    assert sensor.readings == [first, second]
    assert first.sensor is sensor
    assert second.sensor is sensor


def test_sensor_readings_persist_in_sqlite():
    """SQLite creates and persists readings with UTC timestamp semantics."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            organization = Organization(name="Acme Manufacturing")
            plant = Plant(organization_id=organization.id, name="North Plant")
            line = ProductionLine(plant_id=plant.id, name="Assembly Line 1")
            machine = Machine(line.id, "CNC-001", "CNC Mill", "CNC")
            sensor = Sensor(machine.id, "TEMP-001", "Bearing Temperature", "temperature", "°C")
            reading = SensorReading(sensor_id=sensor.id, value=24.5)
            session.add_all([organization, plant, line, machine, sensor, reading])
            session.commit()

            stored = session.get(SensorReading, reading.id)
            assert stored is not None
            assert stored.sensor_id == sensor.id
            assert stored.value == 24.5
            # SQLite drops timezone metadata for DateTime(timezone=True); the
            # model's application-side timestamp remains explicitly UTC-aware.
            assert stored.recorded_at.replace(tzinfo=timezone.utc) == reading.recorded_at
            assert stored.sensor.id == sensor.id
    finally:
        engine.dispose()


def test_complete_six_table_domain_schema_can_be_created_with_sqlite():
    """All six domain tables are registered and can be created in SQLite."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    try:
        Base.metadata.create_all(engine)

        table_names = set(inspect(engine).get_table_names())
        assert {
            "organizations",
            "plants",
            "production_lines",
            "machines",
            "sensors",
            "sensor_readings",
        } <= table_names
    finally:
        engine.dispose()
