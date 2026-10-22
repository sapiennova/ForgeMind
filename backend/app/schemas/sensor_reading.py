"""Pydantic schemas for sensor reading ingestion and responses."""

import math
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


def _normalize_utc(value: datetime) -> datetime:
    """Interpret naive timestamps as UTC and convert aware timestamps to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SensorReadingCreate(BaseModel):
    """Client-controlled fields accepted when ingesting a sensor measurement."""

    model_config = ConfigDict(extra="forbid")

    value: float
    recorded_at: datetime | None = None

    @field_validator("value")
    @classmethod
    def require_finite_value(cls, value: float) -> float:
        """Reject NaN and infinities before persistence."""
        if not math.isfinite(value):
            raise ValueError("value must be a finite number")
        return value

    @field_validator("recorded_at")
    @classmethod
    def normalize_input_timestamp(cls, value: datetime | None) -> datetime | None:
        """Normalize explicit timestamps; omitted timestamps retain the model default."""
        return _normalize_utc(value) if value is not None else None


class SensorReadingResponse(BaseModel):
    """Public representation of a persisted sensor measurement."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    value: float
    recorded_at: datetime

    @field_validator("recorded_at", mode="before")
    @classmethod
    def normalize_recorded_at_timezone(cls, value: datetime) -> datetime:
        """Serialize naive database timestamps as UTC and normalize aware ones."""
        if isinstance(value, datetime):
            return _normalize_utc(value)
        return value


class SensorReadingCreatedResponse(SensorReadingResponse):
    """Public response for a newly ingested reading, including its sensor UUID."""

    sensor_id: UUID


class SensorReadingsResponse(BaseModel):
    """Paginated sensor readings for one sensor."""

    sensor_id: UUID
    readings: list[SensorReadingResponse]
    limit: int
    offset: int
