"""Role requirement (hiring role) model produced by the Requirement Intake module.

Multi-tenant: every row carries company_id. AI-derived outputs (structured JD,
stated/hidden filters) are stored as JSON, never prose-only. Hidden filters are
internal-only and must never be surfaced in externally rendered JD text.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RoleRequirement(Base):
    """A hiring role captured from a raw brief and structured for the pipeline."""

    __tablename__ = "role_requirements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_brief: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="intake_complete")

    # Structured filters: separation of external (stated) vs internal (hidden) rules.
    stated_filters: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    hidden_filters: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Structured job description (never contains hidden rules).
    job_description: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Provenance for the AI/heuristic extraction step.
    llm_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

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
