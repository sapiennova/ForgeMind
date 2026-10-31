"""Shared deterministic fixtures for sensor-health unit tests."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from backend.app.models.sensor_reading import SensorReading


@pytest.fixture
def sensor():
    """Provide a lightweight sensor-like object without database involvement."""
    return SimpleNamespace(id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))


@pytest.fixture
def make_readings():
    """Build readings at controlled one-second intervals."""
    sensor_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    origin = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)

    def factory(values, start=origin, interval_seconds=1):
        return [
            SensorReading(
                sensor_id=sensor_id,
                value=value,
                recorded_at=start + timedelta(seconds=index * interval_seconds),
            )
            for index, value in enumerate(values)
        ]

    return factory
