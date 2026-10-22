"""API tests for the read-only sensor readings endpoint."""

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
    """Provide an isolated in-memory SQLite database for each API test."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )

    def override_get_db():
        with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _create_sensor(api_client: TestClient) -> UUID:
    """Create a complete domain hierarchy in the test database."""
    dependency = api_client.app.dependency_overrides[get_db]()
    session = next(dependency)
    try:
        organization = Organization(name="Test Organization")
        plant = Plant(organization_id=organization.id, name="Test Plant")
        line = ProductionLine(plant_id=plant.id, name="Test Line")
        machine = Machine(line.id, "ASSET-001", "Test Machine", "CNC")
        sensor = Sensor(machine.id, "TEMP-001", "Bearing Temperature", "temperature", "°C")
        session.add_all([organization, plant, line, machine, sensor])
        session.commit()
        return sensor.id
    finally:
        dependency.close()


def _add_readings(
    api_client: TestClient,
    sensor_id: UUID,
    readings: list[tuple[float, datetime]],
) -> list[UUID]:
    """Persist readings and return their generated IDs."""
    dependency = api_client.app.dependency_overrides[get_db]()
    session = next(dependency)
    try:
        models = [
            SensorReading(sensor_id=sensor_id, value=value, recorded_at=recorded_at)
            for value, recorded_at in readings
        ]
        session.add_all(models)
        session.commit()
        return [reading.id for reading in models]
    finally:
        dependency.close()


def test_get_sensor_readings_returns_serialized_readings(api_client):
    sensor_id = _create_sensor(api_client)
    recorded_at = datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc)
    _add_readings(api_client, sensor_id, [(42.5, recorded_at)])

    response = api_client.get(f"/api/v1/sensors/{sensor_id}/readings")

    assert response.status_code == 200
    body = response.json()
    assert body["sensor_id"] == str(sensor_id)
    assert body["limit"] == 100
    assert body["offset"] == 0
    assert len(body["readings"]) == 1
    reading = body["readings"][0]
    assert set(reading) == {"id", "value", "recorded_at"}
    assert UUID(reading["id"])
    assert reading["value"] == 42.5
    serialized_timestamp = datetime.fromisoformat(
        reading["recorded_at"].replace("Z", "+00:00")
    )
    assert serialized_timestamp == recorded_at


def test_existing_sensor_without_readings_returns_empty_collection(api_client):
    sensor_id = _create_sensor(api_client)

    response = api_client.get(f"/api/v1/sensors/{sensor_id}/readings")

    assert response.status_code == 200
    assert response.json()["readings"] == []


def test_readings_are_newest_first_and_paginated(api_client):
    sensor_id = _create_sensor(api_client)
    _add_readings(
        api_client,
        sensor_id,
        [
            (1.0, datetime(2026, 1, 1, tzinfo=timezone.utc)),
            (2.0, datetime(2026, 1, 2, tzinfo=timezone.utc)),
            (3.0, datetime(2026, 1, 3, tzinfo=timezone.utc)),
        ],
    )

    first_page = api_client.get(f"/api/v1/sensors/{sensor_id}/readings?limit=2&offset=0")
    second_page = api_client.get(f"/api/v1/sensors/{sensor_id}/readings?limit=2&offset=2")

    assert [item["value"] for item in first_page.json()["readings"]] == [3.0, 2.0]
    assert [item["value"] for item in second_page.json()["readings"]] == [1.0]
    assert first_page.json()["limit"] == 2
    assert first_page.json()["offset"] == 0
    assert second_page.json()["offset"] == 2


def test_equal_timestamps_have_deterministic_uuid_order(api_client):
    sensor_id = _create_sensor(api_client)
    timestamp = datetime(2026, 2, 1, tzinfo=timezone.utc)
    reading_ids = _add_readings(
        api_client,
        sensor_id,
        [(10.0, timestamp), (20.0, timestamp), (30.0, timestamp)],
    )

    response = api_client.get(f"/api/v1/sensors/{sensor_id}/readings")

    expected_ids = sorted((str(reading_id) for reading_id in reading_ids), reverse=True)
    assert [item["id"] for item in response.json()["readings"]] == expected_ids


@pytest.mark.parametrize("query", ["limit=0", "limit=501", "limit=-1", "offset=-1"])
def test_invalid_pagination_returns_422(api_client, query):
    sensor_id = _create_sensor(api_client)

    response = api_client.get(f"/api/v1/sensors/{sensor_id}/readings?{query}")

    assert response.status_code == 422


def test_malformed_sensor_uuid_returns_422(api_client):
    response = api_client.get("/api/v1/sensors/not-a-uuid/readings")

    assert response.status_code == 422


def test_nonexistent_sensor_returns_404(api_client):
    missing_sensor_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

    response = api_client.get(f"/api/v1/sensors/{missing_sensor_id}/readings")

    assert response.status_code == 404
    assert response.json()["detail"] == "Sensor not found"


def test_post_sensor_reading_creates_and_persists_reading(api_client):
    sensor_id = _create_sensor(api_client)

    response = api_client.post(
        f"/api/v1/sensors/{sensor_id}/readings",
        json={"value": 42.5},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "sensor_id", "value", "recorded_at"}
    assert UUID(body["id"])
    assert body["sensor_id"] == str(sensor_id)
    assert body["value"] == 42.5
    created_at = datetime.fromisoformat(body["recorded_at"].replace("Z", "+00:00"))
    assert created_at.tzinfo is not None
    assert created_at.utcoffset().total_seconds() == 0

    listed = api_client.get(f"/api/v1/sensors/{sensor_id}/readings")
    assert listed.status_code == 200
    assert len(listed.json()["readings"]) == 1
    assert listed.json()["readings"][0]["id"] == body["id"]
    assert listed.json()["readings"][0]["value"] == 42.5


def test_post_sensor_reading_uses_model_timestamp_default(api_client):
    sensor_id = _create_sensor(api_client)
    before = datetime.now(timezone.utc)

    response = api_client.post(
        f"/api/v1/sensors/{sensor_id}/readings",
        json={"value": 7.25},
    )

    after = datetime.now(timezone.utc)
    assert response.status_code == 201
    recorded_at = datetime.fromisoformat(
        response.json()["recorded_at"].replace("Z", "+00:00")
    )
    assert before <= recorded_at <= after


def test_post_sensor_reading_normalizes_explicit_timestamp_to_utc(api_client):
    sensor_id = _create_sensor(api_client)

    response = api_client.post(
        f"/api/v1/sensors/{sensor_id}/readings",
        json={"value": 12, "recorded_at": "2026-10-20T15:30:00+03:00"},
    )

    assert response.status_code == 201
    recorded_at = datetime.fromisoformat(
        response.json()["recorded_at"].replace("Z", "+00:00")
    )
    assert recorded_at == datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc)


def test_post_sensor_reading_interprets_naive_timestamp_as_utc(api_client):
    sensor_id = _create_sensor(api_client)

    response = api_client.post(
        f"/api/v1/sensors/{sensor_id}/readings",
        json={"value": 12, "recorded_at": "2026-10-20T12:30:00"},
    )

    assert response.status_code == 201
    recorded_at = datetime.fromisoformat(
        response.json()["recorded_at"].replace("Z", "+00:00")
    )
    assert recorded_at == datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc)


def test_post_sensor_reading_rejects_malformed_sensor_uuid(api_client):
    response = api_client.post(
        "/api/v1/sensors/not-a-uuid/readings",
        json={"value": 1},
    )
    assert response.status_code == 422


def test_post_sensor_reading_returns_404_for_unknown_sensor(api_client):
    response = api_client.post(
        "/api/v1/sensors/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/readings",
        json={"value": 1},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Sensor not found"


@pytest.mark.parametrize("payload", [{}, {"value": None}, {"value": "not-a-number"}])
def test_post_sensor_reading_rejects_missing_or_invalid_value(api_client, payload):
    sensor_id = _create_sensor(api_client)
    response = api_client.post(f"/api/v1/sensors/{sensor_id}/readings", json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_post_sensor_reading_rejects_non_finite_values(api_client, value):
    sensor_id = _create_sensor(api_client)
    response = api_client.post(
        f"/api/v1/sensors/{sensor_id}/readings",
        json={"value": value},
    )
    assert response.status_code == 422


def test_post_sensor_reading_rejects_invalid_timestamp(api_client):
    sensor_id = _create_sensor(api_client)
    response = api_client.post(
        f"/api/v1/sensors/{sensor_id}/readings",
        json={"value": 1, "recorded_at": "not-a-timestamp"},
    )
    assert response.status_code == 422


def test_post_sensor_reading_does_not_accept_internal_fields(api_client):
    sensor_id = _create_sensor(api_client)
    response = api_client.post(
        f"/api/v1/sensors/{sensor_id}/readings",
        json={
            "value": 1,
            "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "sensor_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        },
    )
    assert response.status_code == 422
