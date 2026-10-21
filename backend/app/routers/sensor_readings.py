"""Read-only API endpoints for persisted sensor readings."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.sensor import Sensor
from backend.app.models.sensor_reading import SensorReading
from backend.app.schemas.sensor_reading import (
    SensorReadingResponse,
    SensorReadingsResponse,
)

router = APIRouter(prefix="/api/v1/sensors", tags=["sensor readings"])

DEFAULT_READING_LIMIT = 100
MAX_READING_LIMIT = 500


@router.get(
    "/{sensor_id}/readings",
    response_model=SensorReadingsResponse,
    summary="List persisted readings for a sensor",
)
def list_sensor_readings(
    sensor_id: UUID,
    limit: int = Query(
        default=DEFAULT_READING_LIMIT,
        ge=1,
        le=MAX_READING_LIMIT,
        description=f"Maximum number of readings to return (1-{MAX_READING_LIMIT}).",
    ),
    offset: int = Query(default=0, ge=0, description="Number of newest readings to skip."),
    db: Session = Depends(get_db),
) -> SensorReadingsResponse:
    """Return readings newest-first, with UUID tie-breaking for stable pagination."""
    if db.get(Sensor, sensor_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor not found",
        )

    statement = (
        select(SensorReading)
        .where(SensorReading.sensor_id == sensor_id)
        .order_by(desc(SensorReading.recorded_at), desc(SensorReading.id))
        .offset(offset)
        .limit(limit)
    )
    readings = db.scalars(statement).all()

    return SensorReadingsResponse(
        sensor_id=sensor_id,
        readings=[SensorReadingResponse.model_validate(item) for item in readings],
        limit=limit,
        offset=offset,
    )
