"""Pydantic response schemas for sensor readings."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SensorReadingResponse(BaseModel):
    """Public representation of a persisted sensor measurement."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    value: float
    recorded_at: datetime


class SensorReadingsResponse(BaseModel):
    """Paginated sensor readings for one sensor."""

    sensor_id: UUID
    readings: list[SensorReadingResponse]
    limit: int
    offset: int
