"""Production line domain model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class ProductionLine(Base):
    """Production line owned by a plant."""

    __tablename__ = "production_lines"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    plant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("plants.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    plant: Mapped["Plant"] = relationship("Plant", back_populates="production_lines")
    machines: Mapped[list["Machine"]] = relationship("Machine", back_populates="production_line")

    def __init__(self, plant_id: UUID, name: str) -> None:
        """Create a production line with application-generated metadata."""
        self.id = uuid4()
        self.plant_id = plant_id
        self.name = name
        self.created_at = _utc_now()
