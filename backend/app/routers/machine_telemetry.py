"""Read-only machine telemetry summary endpoint."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.machine import Machine
from backend.app.models.sensor import Sensor
from backend.app.models.sensor_reading import SensorReading
from backend.app.schemas.machine_telemetry import (
    MachineTelemetryResponse,
    SensorTelemetrySummary,
)

router = APIRouter(prefix="/api/v1/machines", tags=["machine telemetry"])


@router.get(
    "/{machine_id}/telemetry",
    response_model=MachineTelemetryResponse,
    summary="Summarize telemetry for a machine",
)
def get_machine_telemetry(
    machine_id: UUID,
    db: Session = Depends(get_db),
) -> MachineTelemetryResponse:
    """Return per-sensor reading counts and latest values without loading history."""
    if db.get(Machine, machine_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Machine not found",
        )

    reading_count = (
        select(func.count(SensorReading.id))
        .where(SensorReading.sensor_id == Sensor.id)
        .correlate(Sensor)
        .scalar_subquery()
    )
    latest_value = (
        select(SensorReading.value)
        .where(SensorReading.sensor_id == Sensor.id)
        .order_by(desc(SensorReading.recorded_at), desc(SensorReading.id))
        .limit(1)
        .correlate(Sensor)
        .scalar_subquery()
    )
    latest_timestamp = (
        select(SensorReading.recorded_at)
        .where(SensorReading.sensor_id == Sensor.id)
        .order_by(desc(SensorReading.recorded_at), desc(SensorReading.id))
        .limit(1)
        .correlate(Sensor)
        .scalar_subquery()
    )

    statement = (
        select(Sensor, reading_count, latest_value, latest_timestamp)
        .where(Sensor.machine_id == machine_id)
        .order_by(Sensor.id)
    )
    rows = db.execute(statement).all()

    return MachineTelemetryResponse(
        machine_id=machine_id,
        sensors=[
            SensorTelemetrySummary(
                sensor_id=sensor.id,
                name=sensor.name,
                sensor_type=sensor.sensor_type,
                unit=sensor.unit,
                reading_count=count,
                latest_reading_value=value,
                latest_reading_timestamp=timestamp,
            )
            for sensor, count, value, timestamp in rows
        ],
    )
