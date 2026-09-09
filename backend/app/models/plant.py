"""Plant domain model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Plant(Base):
    """Industrial plant owned by an organization."""

    __tablename__ = "plants"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="plants")

    def __init__(self, organization_id: UUID, name: str) -> None:
        """Create a plant with application-generated metadata."""
        self.id = uuid4()
        self.organization_id = organization_id
        self.name = name
        self.created_at = _utc_now()
