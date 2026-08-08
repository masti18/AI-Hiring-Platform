"""Sourced candidate model.

Candidates are sourced for a role requirement and scored against the role's
stated and hidden rules. The score is stored as structured JSON (never
prose-only). Candidate records are internal recruiter data; hidden-rule
evaluation lives here and is never exposed on any external/candidate-facing view.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Candidate(Base):
    """A candidate sourced for a role, with a structured score attached."""

    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("role_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sourcing_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sourcing_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="mock")
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Structured candidate attributes used for rule evaluation.
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Structured score output (stated/hidden results, overall, qualification).
    score: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="sourced")

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
