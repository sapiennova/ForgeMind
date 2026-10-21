"""Individual sensor measurement model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class SensorReading(Base):
    """A single measurement recorded by a physical sensor."""

    __tablename__ = "sensor_readings"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    sensor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sensors.id"),
        nullable=False,
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    sensor: Mapped["Sensor"] = relationship("Sensor", back_populates="readings")

    def __init__(
        self,
        sensor_id: UUID,
        value: float,
        recorded_at: datetime | None = None,
    ) -> None:
        """Create a reading with an application-generated ID and UTC timestamp."""
        self.id = uuid4()
        self.sensor_id = sensor_id
        self.value = value
        self.recorded_at = recorded_at if recorded_at is not None else _utc_now()
