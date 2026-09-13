"""Machine domain model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Machine(Base):
    """Physical industrial asset assigned to a production line."""

    __tablename__ = "machines"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    production_line_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("production_lines.id"),
        nullable=False,
    )
    asset_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    machine_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    production_line: Mapped["ProductionLine"] = relationship(
        "ProductionLine", back_populates="machines"
    )

    def __init__(
        self,
        production_line_id: UUID,
        asset_id: str,
        name: str,
        machine_type: str,
        status: str = "active",
    ) -> None:
        """Create a machine with application-generated metadata."""
        self.id = uuid4()
        self.production_line_id = production_line_id
        self.asset_id = asset_id
        self.name = name
        self.machine_type = machine_type
        self.status = status
        self.created_at = _utc_now()
