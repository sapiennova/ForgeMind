"""Tests for the persistent sensor calibration record model."""

import math
import os
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import (
    Machine,
    Organization,
    Plant,
    ProductionLine,
    Sensor,
    SensorCalibration,
)
from backend.app.models.base import Base

_CALIBRATION_DATE = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)


def _sensor() -> Sensor:
    """Create an unsaved sensor for in-memory relationship tests."""
    organization = Organization(name="Acme Manufacturing")
    plant = Plant(organization_id=organization.id, name="North Plant")
    production_line = ProductionLine(plant_id=plant.id, name="Assembly Line 1")
    machine = Machine(production_line.id, "CNC-001", "CNC Mill", "CNC")
    return Sensor(machine.id, "TEMP-001", "Bearing Temperature", "temperature", "°C")


def _calibration(sensor_id: UUID, **overrides: object) -> SensorCalibration:
    """Create a calibration with valid defaults and optional overrides."""
    values: dict[str, object] = {
        "reference_value": 100.0,
        "measured_value": 99.5,
        "offset": 0.5,
        "calibration_factor": 1.005,
        "technician": "A. Technician",
        "calibration_date": _CALIBRATION_DATE,
        "result": "PASSED",
    }
    values.update(overrides)
    return SensorCalibration(sensor_id=sensor_id, **values)  # type: ignore[arg-type]


def _sqlite_engine():
    """Create all domain tables with SQLite foreign-key enforcement enabled."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, connection_record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine


def _persist_sensor(session: Session) -> Sensor:
    """Persist the industrial hierarchy needed by a sensor foreign key."""
    organization = Organization(name="Acme Manufacturing")
    plant = Plant(organization_id=organization.id, name="North Plant")
    production_line = ProductionLine(plant_id=plant.id, name="Assembly Line 1")
    machine = Machine(production_line.id, "CNC-001", "CNC Mill", "CNC")
    sensor = Sensor(machine.id, "TEMP-001", "Bearing Temperature", "temperature", "°C")
    session.add_all([organization, plant, production_line, machine, sensor])
    session.commit()
    return sensor


def test_sensor_calibration_stores_calibration_measurements_and_metadata():
    """Calibration records preserve supplied measurements and metadata."""
    sensor = _sensor()
    due_date = datetime(2027, 1, 15, 12, tzinfo=timezone.utc)
    record = _calibration(
        sensor.id,
        reference_value=100.25,
        measured_value=99.75,
        offset=0.5,
        calibration_factor=1.01,
        technician="A. Technician",
        next_calibration_due=due_date,
        notes="Bearing temperature probe checked against reference instrument.",
    )

    assert record.sensor_id == sensor.id
    assert record.reference_value == 100.25
    assert record.measured_value == 99.75
    assert record.offset == 0.5
    assert record.calibration_factor == 1.01
    assert record.technician == "A. Technician"
    assert record.calibration_date == _CALIBRATION_DATE
    assert record.next_calibration_due == due_date
    assert record.result == "PASSED"
    assert record.notes == "Bearing temperature probe checked against reference instrument."


def test_sensor_calibrations_receive_distinct_uuid_ids():
    """Each calibration receives its own application-generated UUID."""
    sensor_id = _sensor().id
    first = _calibration(sensor_id)
    second = _calibration(sensor_id)

    assert isinstance(first.id, UUID)
    assert isinstance(second.id, UUID)
    assert first.id != second.id


def test_sensor_calibration_created_at_defaults_to_timezone_aware_utc():
    """Calibration creation timestamps are generated in UTC."""
    record = _calibration(_sensor().id)

    assert record.created_at is not None
    assert record.created_at.tzinfo is not None
    assert record.created_at.utcoffset() == timezone.utc.utcoffset(record.created_at)


def test_sensor_to_calibration_relationship_works_in_both_directions():
    """Sensors expose calibration records and each record exposes its sensor."""
    sensor = _sensor()
    record = _calibration(sensor.id)

    sensor.calibrations.append(record)

    assert sensor.calibrations == [record]
    assert record.sensor is sensor


def test_sensor_can_have_multiple_calibration_records():
    """A sensor can have more than one calibration record."""
    sensor = _sensor()
    first = _calibration(sensor.id)
    second = _calibration(
        sensor.id,
        calibration_date=datetime(2026, 2, 15, 12, tzinfo=timezone.utc),
        result="FAILED",
    )

    sensor.calibrations.extend([first, second])

    assert sensor.calibrations == [first, second]
    assert first.sensor is sensor
    assert second.sensor is sensor


def test_calibration_history_remains_intact_when_a_new_record_is_added():
    """Persisting a newer calibration does not replace earlier history."""
    engine = _sqlite_engine()
    try:
        with Session(engine) as session:
            sensor = _persist_sensor(session)
            first = _calibration(sensor.id)
            session.add(first)
            session.commit()

            second = _calibration(
                sensor.id,
                calibration_date=datetime(2026, 2, 15, 12, tzinfo=timezone.utc),
                result="FAILED",
            )
            session.add(second)
            session.commit()

            history = session.scalars(
                select(SensorCalibration).where(SensorCalibration.sensor_id == sensor.id)
            ).all()

            assert len(history) == 2
            assert {record.id for record in history} == {first.id, second.id}
    finally:
        engine.dispose()


def test_invalid_calibration_result_is_rejected():
    """Only PASSED and FAILED are valid calibration outcomes."""
    with pytest.raises(ValueError, match="result"):
        _calibration(_sensor().id, result="IN_PROGRESS")


@pytest.mark.parametrize(
    "field",
    ("reference_value", "measured_value", "offset", "calibration_factor"),
)
@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_non_finite_measurements_are_rejected(field: str, value: float):
    """All calibration measurements reject NaN and positive or negative infinity."""
    with pytest.raises(ValueError, match=field):
        _calibration(_sensor().id, **{field: value})


@pytest.mark.parametrize(
    "field",
    (
        "sensor_id",
        "reference_value",
        "measured_value",
        "offset",
        "calibration_factor",
        "technician",
        "calibration_date",
        "result",
    ),
)
def test_required_calibration_fields_reject_null_values(field: str):
    """Required calibration fields cannot be initialized with null values."""
    values = {
        "sensor_id": uuid4(),
        "reference_value": 100.0,
        "measured_value": 99.5,
        "offset": 0.5,
        "calibration_factor": 1.005,
        "technician": "A. Technician",
        "calibration_date": _CALIBRATION_DATE,
        "result": "PASSED",
    }
    values[field] = None

    with pytest.raises(ValueError):
        SensorCalibration(**values)  # type: ignore[arg-type]


def test_due_date_earlier_than_calibration_date_is_rejected():
    """A next due date cannot precede the calibration that sets it."""
    earlier_due_date = _CALIBRATION_DATE - timedelta(days=1)

    with pytest.raises(ValueError, match="next_calibration_due"):
        _calibration(_sensor().id, next_calibration_due=earlier_due_date)


def test_optional_notes_and_next_calibration_due_can_be_omitted():
    """Notes and the next due date are optional calibration metadata."""
    record = _calibration(_sensor().id)

    assert record.notes is None
    assert record.next_calibration_due is None
    assert SensorCalibration.__table__.c.notes.nullable is True
    assert SensorCalibration.__table__.c.next_calibration_due.nullable is True


def test_calibration_sensor_foreign_key_is_enforced_by_sqlite():
    """SQLite rejects calibration records that reference a missing sensor."""
    engine = _sqlite_engine()
    try:
        with Session(engine) as session:
            invalid_record = _calibration(uuid4())
            session.add(invalid_record)

            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        engine.dispose()


def test_required_calibration_columns_are_non_nullable():
    """The database schema marks every required calibration field as non-null."""
    required_fields = (
        "id",
        "sensor_id",
        "reference_value",
        "measured_value",
        "offset",
        "calibration_factor",
        "technician",
        "calibration_date",
        "result",
        "created_at",
    )

    assert all(not SensorCalibration.__table__.c[field].nullable for field in required_fields)


def test_calibration_result_check_constraint_is_enforced_by_sqlite():
    """The database independently rejects unsupported result values."""
    engine = _sqlite_engine()
    try:
        with Session(engine) as session:
            sensor = _persist_sensor(session)
            values = {
                "id": uuid4(),
                "sensor_id": sensor.id,
                "reference_value": 100.0,
                "measured_value": 99.5,
                "offset": 0.5,
                "calibration_factor": 1.005,
                "technician": "A. Technician",
                "calibration_date": _CALIBRATION_DATE,
                "next_calibration_due": None,
                "result": "IN_PROGRESS",
                "notes": None,
                "created_at": _CALIBRATION_DATE,
            }

            with pytest.raises(IntegrityError):
                session.execute(SensorCalibration.__table__.insert().values(**values))
            session.rollback()
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "field",
    ("reference_value", "measured_value", "offset", "calibration_factor"),
)
@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_database_rejects_non_finite_measurements(field: str, value: float):
    """Database checks reject non-finite values even when ORM validators are bypassed."""
    engine = _sqlite_engine()
    try:
        with Session(engine) as session:
            sensor = _persist_sensor(session)
            values = {
                "id": uuid4(),
                "sensor_id": sensor.id,
                "reference_value": 100.0,
                "measured_value": 99.5,
                "offset": 0.5,
                "calibration_factor": 1.005,
                "technician": "A. Technician",
                "calibration_date": _CALIBRATION_DATE,
                "next_calibration_due": None,
                "result": "PASSED",
                "notes": None,
                "created_at": _CALIBRATION_DATE,
            }
            values[field] = value

            with pytest.raises(IntegrityError):
                session.execute(SensorCalibration.__table__.insert().values(**values))
            session.rollback()
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("next_due", "should_raise"),
    (
        (datetime(2026, 1, 15, 13, tzinfo=timezone.utc), False),
        (datetime(2026, 1, 15, 11, tzinfo=timezone.utc), True),
    ),
    ids=("accepts-later-due-date", "rejects-earlier-due-date"),
)
def test_reloaded_sqlite_calibration_compares_naive_dates_as_utc(
    next_due: datetime,
    should_raise: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    """Date validation treats SQLite-loaded naive timestamps as UTC, not local time."""
    if not hasattr(time, "tzset"):
        pytest.skip("Changing the process timezone requires time.tzset().")

    original_timezone = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "Etc/GMT-5")
    time.tzset()

    engine = _sqlite_engine()
    try:
        with Session(engine) as session:
            sensor = _persist_sensor(session)
            record = _calibration(sensor.id, calibration_date=_CALIBRATION_DATE)
            session.add(record)
            session.commit()

            record_id = record.id
            session.expunge_all()
            reloaded = session.get(SensorCalibration, record_id)

            assert reloaded is not None
            assert reloaded.calibration_date == _CALIBRATION_DATE.replace(tzinfo=None)
            assert reloaded.calibration_date.tzinfo is None

            if should_raise:
                with pytest.raises(
                    ValueError,
                    match="next_calibration_due cannot be earlier than calibration_date",
                ):
                    reloaded.next_calibration_due = next_due
            else:
                reloaded.next_calibration_due = next_due
                assert reloaded.next_calibration_due == next_due
    finally:
        engine.dispose()
        if original_timezone is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", original_timezone)
        time.tzset()
