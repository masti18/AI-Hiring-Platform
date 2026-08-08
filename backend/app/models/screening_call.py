"""AI screening call model (Milestone 3).

Records one AI-driven screening call for a candidate: the structured transcript,
a structured evaluation (scores + reasoning as JSON, never prose-only), and the
post-AI-call auto-gate (gate2) decision. Voice/LLM integrations stay behind
adapters; this row is the durable, auditable output of the stage.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScreeningCall(Base):
    """A structured AI screening call + evaluation for a candidate."""

    __tablename__ = "screening_calls"

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
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed")

    # Structured transcript: list of {"speaker": ..., "text": ...} turns.
    transcript: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Structured evaluation (dimensions, overall, recommendation, reasoning).
    evaluation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recommendation: Mapped[str] = mapped_column(String(50), nullable=False, default="reject")

    # Structured post-AI-call gate (gate2) decision.
    gate2_decision: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Provider/transport metadata for the (mockable) voice + LLM stack.
    providers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

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
