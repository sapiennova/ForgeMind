
"""Pydantic response schemas for sensor readings."""

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class SensorReadingResponse(BaseModel):
    """Public representation of a persisted sensor measurement."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    value: float
    recorded_at: datetime

    @field_validator("recorded_at", mode="before")
    @classmethod
    def normalize_recorded_at_timezone(cls, value: datetime) -> datetime:
        """Treat naive database timestamps as UTC."""
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class SensorReadingsResponse(BaseModel):
    """Paginated sensor readings for one sensor."""

    sensor_id: UUID
    readings: list[SensorReadingResponse]
    limit: int
    offset: int
