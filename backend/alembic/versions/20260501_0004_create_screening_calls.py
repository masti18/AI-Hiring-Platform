"""create screening_calls table

Revision ID: 20260501_0004
Revises: 20260415_0003
Create Date: 2026-05-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260501_0004"
down_revision: str | None = "20260415_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "screening_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_requirement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="completed"),
        sa.Column(
            "transcript",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "evaluation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recommendation", sa.String(length=50), nullable=False, server_default="reject"),
        sa.Column(
            "gate2_decision",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "providers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["role_requirement_id"], ["role_requirements.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_screening_calls_company_id", "screening_calls", ["company_id"], unique=False
    )
    op.create_index(
        "ix_screening_calls_role_requirement_id",
        "screening_calls",
        ["role_requirement_id"],
        unique=False,
    )
    op.create_index(
        "ix_screening_calls_candidate_id", "screening_calls", ["candidate_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_screening_calls_candidate_id", table_name="screening_calls")
    op.drop_index("ix_screening_calls_role_requirement_id", table_name="screening_calls")
    op.drop_index("ix_screening_calls_company_id", table_name="screening_calls")
    op.drop_table("screening_calls")
