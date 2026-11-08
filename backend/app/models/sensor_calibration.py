"""Historical sensor calibration record model."""

import math
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.app.models.base import Base

_MAX_FINITE_FLOAT = "1.7976931348623157e308"
_MEASUREMENT_FIELDS = (
    "reference_value",
    "measured_value",
    "offset",
    "calibration_factor",
)


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Interpret naive timestamps as UTC and normalize aware values to UTC.

    SQLite does not preserve timezone metadata for DateTime columns, so a
    datetime reloaded from SQLite is naive even when it was originally UTC.
    Treat those values as UTC rather than relying on the machine-local timezone.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SensorCalibration(Base):
    """A persisted record of one calibration performed on a sensor."""

    __tablename__ = "sensor_calibrations"
    __table_args__ = (
        CheckConstraint(
            "result IN ('PASSED', 'FAILED')",
            name="ck_sensor_calibrations_result",
        ),
        *(
            CheckConstraint(
                f"{field} >= -{_MAX_FINITE_FLOAT} AND "
                f"{field} <= {_MAX_FINITE_FLOAT}",
                name=f"ck_sensor_calibrations_{field}_finite",
            )
            for field in _MEASUREMENT_FIELDS
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    sensor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sensors.id"),
        nullable=False,
    )
    reference_value: Mapped[float] = mapped_column(Float, nullable=False)
    measured_value: Mapped[float] = mapped_column(Float, nullable=False)
    offset: Mapped[float] = mapped_column(Float, nullable=False)
    calibration_factor: Mapped[float] = mapped_column(Float, nullable=False)
    technician: Mapped[str] = mapped_column(String, nullable=False)
    calibration_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    next_calibration_due: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    result: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    sensor: Mapped["Sensor"] = relationship("Sensor", back_populates="calibrations")

    def __init__(
        self,
        sensor_id: UUID,
        reference_value: float,
        measured_value: float,
        offset: float,
        calibration_factor: float,
        technician: str,
        calibration_date: datetime,
        result: str,
        next_calibration_due: datetime | None = None,
        notes: str | None = None,
    ) -> None:
        """Create a record while generating its identifier and UTC timestamp."""
        self.id = uuid4()
        self.sensor_id = sensor_id
        self.reference_value = reference_value
        self.measured_value = measured_value
        self.offset = offset
        self.calibration_factor = calibration_factor
        self.technician = technician
        self.calibration_date = calibration_date
        self.next_calibration_due = next_calibration_due
        self.result = result
        self.notes = notes
        self.created_at = _utc_now()

    @validates("sensor_id")
    def validate_sensor_id(self, key: str, value: UUID) -> UUID:
        """Prevent a missing sensor reference before database persistence."""
        if value is None:
            raise ValueError("sensor_id is required")
        return value

    @validates(*_MEASUREMENT_FIELDS)
    def validate_finite_measurement(self, key: str, value: float) -> float:
        """Reject values that cannot be represented as finite floating points."""
        try:
            is_finite = not isinstance(value, bool) and math.isfinite(value)
        except (TypeError, ValueError, OverflowError):
            is_finite = False
        if not is_finite:
            raise ValueError(f"{key} must be a finite numeric value")
        return value

    @validates("technician")
    def validate_technician(self, key: str, value: str) -> str:
        """Reject a missing technician while allowing any non-null name."""
        if value is None:
            raise ValueError("technician is required")
        return value

    @validates("result")
    def validate_result(self, key: str, value: str) -> str:
        """Restrict calibration outcomes to the supported result values."""
        if not isinstance(value, str) or value not in {"PASSED", "FAILED"}:
            raise ValueError("result must be either 'PASSED' or 'FAILED'")
        return value

    @validates("calibration_date", "next_calibration_due")
    def validate_calibration_dates(self, key: str, value: datetime | None) -> datetime | None:
        """Require aware timestamps and keep the optional due date chronological."""
        if value is None:
            if key == "calibration_date":
                raise ValueError("calibration_date is required")
            return None

        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{key} must be a timezone-aware datetime")

        if key == "calibration_date":
            due_date = getattr(self, "next_calibration_due", None)
            if due_date is not None and _as_utc(due_date) < _as_utc(value):
                raise ValueError("next_calibration_due cannot be earlier than calibration_date")
        else:
            calibration_date = getattr(self, "calibration_date", None)
            if calibration_date is not None and _as_utc(value) < _as_utc(calibration_date):
                raise ValueError("next_calibration_due cannot be earlier than calibration_date")

        return value
