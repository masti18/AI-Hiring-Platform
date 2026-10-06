"""Open role / requisition with stated vs hidden filters and structured JD output."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Role(Base):
    """Hiring requisition. Hidden filters are internal-only JSON predicates."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")

    # Raw hiring brief + structured intake artifacts
    brief_text: Mapped[str] = mapped_column(Text, nullable=False)
    hiring_brief: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Stated = visible in external JD; hidden = internal predicates only
    stated_filters: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    hidden_filters: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    # AI-generated JD as structured JSON (never prose-only)
    jd: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    company = relationship("Company", backref="roles")
