"""Organization domain model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


def _utc_now() -> datetime:
    """Return the current UTC-aware timestamp."""
    return datetime.now(timezone.utc)


class Organization(Base):
    """Top-level entity in the ForgeMind industrial hierarchy."""

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(
        self,
        name: str,
        id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Initialize an organization with application-generated defaults."""
        self.id = id or uuid4()
        self.name = name
        self.created_at = created_at or _utc_now()
