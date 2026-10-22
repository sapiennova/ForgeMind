"""Pydantic response schemas for machine telemetry summaries."""

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, field_validator


class SensorTelemetrySummary(BaseModel):
    """Aggregated reading metadata for one sensor."""

    sensor_id: UUID
    name: str
    sensor_type: str
    unit: str
    reading_count: int
    latest_reading_value: float | None
    latest_reading_timestamp: datetime | None

    @field_validator("latest_reading_timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        """Interpret naive database timestamps as UTC and normalize aware values."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class MachineTelemetryResponse(BaseModel):
    """Telemetry summary for a machine and all its sensors."""

    machine_id: UUID
    sensors: list[SensorTelemetrySummary]
