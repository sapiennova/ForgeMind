"""Focused API tests for machine telemetry summaries."""

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import get_db
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.machine import Machine
from backend.app.models.organization import Organization
from backend.app.models.plant import Plant
from backend.app.models.production_line import ProductionLine
from backend.app.models.sensor import Sensor
from backend.app.models.sensor_reading import SensorReading


@pytest.fixture
def api_client():
    """Use a fresh in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(
        bind=engine, class_=Session, autoflush=False, expire_on_commit=False
    )

    def override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _session(api_client):
    """Open a session using the API's test dependency override."""
    dependency = api_client.app.dependency_overrides[get_db]()
    session = next(dependency)
    return dependency, session


def _create_machine(api_client, *, sensors=2):
    dependency, session = _session(api_client)
    try:
        organization = Organization(name="Telemetry Test Org")
        plant = Plant(organization_id=organization.id, name="Telemetry Test Plant")
        line = ProductionLine(plant_id=plant.id, name="Telemetry Test Line")
        machine = Machine(line.id, "TELEMETRY-ASSET", "Telemetry Machine", "CNC")
        sensor_models = [
            Sensor(
                machine.id,
                f"TELEMETRY-{index}",
                f"Sensor {index}",
                "temperature" if index == 1 else "vibration",
                "°C" if index == 1 else "mm/s",
            )
            for index in range(1, sensors + 1)
        ]
        session.add_all([organization, plant, line, machine, *sensor_models])
        session.commit()
        return machine.id, [sensor.id for sensor in sensor_models]
    finally:
        dependency.close()


def _add_readings(api_client, sensor_id, readings):
    dependency, session = _session(api_client)
    try:
        models = [
            SensorReading(sensor_id=sensor_id, value=value, recorded_at=timestamp)
            for value, timestamp, reading_id in readings
        ]
        for model, (_, _, reading_id) in zip(models, readings):
            model.id = reading_id
        session.add_all(models)
        session.commit()
    finally:
        dependency.close()


def test_telemetry_summarizes_multiple_sensors_and_readings(api_client):
    machine_id, sensor_ids = _create_machine(api_client)
    older = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
    newer = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    _add_readings(api_client, sensor_ids[0], [
        (10.0, older, UUID("00000000-0000-4000-8000-000000000001")),
        (15.5, newer, UUID("00000000-0000-4000-8000-000000000002")),
    ])
    _add_readings(api_client, sensor_ids[1], [
        (2.0, older, UUID("00000000-0000-4000-8000-000000000003")),
    ])

    response = api_client.get(f"/api/v1/machines/{machine_id}/telemetry")

    assert response.status_code == 200
    body = response.json()
    assert body["machine_id"] == str(machine_id)
    assert [item["sensor_id"] for item in body["sensors"]] == sorted(
        str(sensor_id) for sensor_id in sensor_ids
    )
    summaries = {item["sensor_id"]: item for item in body["sensors"]}
    first = summaries[str(sensor_ids[0])]
    second = summaries[str(sensor_ids[1])]
    assert first["reading_count"] == 2
    assert first["latest_reading_value"] == 15.5
    assert datetime.fromisoformat(first["latest_reading_timestamp"].replace("Z", "+00:00")) == newer
    assert second["reading_count"] == 1
    assert second["latest_reading_value"] == 2.0


def test_sensor_without_readings_is_present_with_null_latest_fields(api_client):
    machine_id, sensor_ids = _create_machine(api_client, sensors=1)

    response = api_client.get(f"/api/v1/machines/{machine_id}/telemetry")

    assert response.status_code == 200
    assert response.json()["sensors"] == [{
        "sensor_id": str(sensor_ids[0]),
        "name": "Sensor 1",
        "sensor_type": "temperature",
        "unit": "°C",
        "reading_count": 0,
        "latest_reading_value": None,
        "latest_reading_timestamp": None,
    }]


def test_machine_without_sensors_returns_empty_list(api_client):
    machine_id, _ = _create_machine(api_client, sensors=0)

    response = api_client.get(f"/api/v1/machines/{machine_id}/telemetry")

    assert response.status_code == 200
    assert response.json() == {"machine_id": str(machine_id), "sensors": []}


def test_unknown_machine_returns_404(api_client):
    response = api_client.get(
        "/api/v1/machines/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/telemetry"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Machine not found"


def test_malformed_machine_uuid_returns_422(api_client):
    response = api_client.get("/api/v1/machines/not-a-uuid/telemetry")
    assert response.status_code == 422


def test_equal_timestamps_use_largest_reading_uuid_as_tie_breaker(api_client):
    machine_id, sensor_ids = _create_machine(api_client, sensors=1)
    timestamp = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    _add_readings(api_client, sensor_ids[0], [
        (11.0, timestamp, UUID("00000000-0000-4000-8000-000000000011")),
        (22.0, timestamp, UUID("00000000-0000-4000-8000-000000000022")),
    ])

    response = api_client.get(f"/api/v1/machines/{machine_id}/telemetry")

    assert response.status_code == 200
    summary = response.json()["sensors"][0]
    assert summary["reading_count"] == 2
    assert summary["latest_reading_value"] == 22.0
    actual_timestamp = datetime.fromisoformat(
        summary["latest_reading_timestamp"].replace("Z", "+00:00")
    )
    assert actual_timestamp == timestamp


def test_existing_sensor_readings_get_and_post_still_work(api_client):
    _, sensor_ids = _create_machine(api_client, sensors=1)
    sensor_id = sensor_ids[0]

    created = api_client.post(
        f"/api/v1/sensors/{sensor_id}/readings", json={"value": 42.5}
    )
    assert created.status_code == 201
    assert created.json()["value"] == 42.5

    listed = api_client.get(f"/api/v1/sensors/{sensor_id}/readings")
    assert listed.status_code == 200
    assert listed.json()["readings"][0]["value"] == 42.5
