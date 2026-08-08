"""Sourcing run model.

Records one execution of the sourcing + scoring stage for a role requirement,
including the post-sourcing auto-gate (gate1) decision. The gate ALWAYS evaluates
and is ALWAYS audited; whether it blocks for a human is config-driven.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SourcingRun(Base):
    """One sourcing/scoring pass over a role, with its gate1 decision."""

    __tablename__ = "sourcing_runs"

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

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed")
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qualified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Structured gate1 decision (gate/action/reasoning/policy_result).
    gate1_decision: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
