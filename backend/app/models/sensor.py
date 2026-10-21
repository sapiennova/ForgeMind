"""Sensor domain model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Sensor(Base):
    """Physical sensor installed on an industrial machine."""

    __tablename__ = "sensors"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    machine_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id"),
        nullable=False,
    )
    sensor_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sensor_type: Mapped[str] = mapped_column(String, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    machine: Mapped["Machine"] = relationship("Machine", back_populates="sensors")
    readings: Mapped[list["SensorReading"]] = relationship(
        "SensorReading", back_populates="sensor"
    )

    def __init__(
        self,
        machine_id: UUID,
        sensor_id: str,
        name: str,
        sensor_type: str,
        unit: str,
        status: str = "active",
    ) -> None:
        """Create a sensor with application-generated metadata."""
        self.id = uuid4()
        self.machine_id = machine_id
        self.sensor_id = sensor_id
        self.name = name
        self.sensor_type = sensor_type
        self.unit = unit
        self.status = status
        self.created_at = _utc_now()
