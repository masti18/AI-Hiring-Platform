"""create sourcing_runs and candidates tables

Revision ID: 20260415_0003
Revises: 20260401_0002
Create Date: 2026-04-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260415_0003"
down_revision: str | None = "20260401_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sourcing_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_requirement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="completed"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qualified_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "gate1_decision",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["role_requirement_id"], ["role_requirements.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sourcing_runs_company_id", "sourcing_runs", ["company_id"], unique=False
    )
    op.create_index(
        "ix_sourcing_runs_role_requirement_id",
        "sourcing_runs",
        ["role_requirement_id"],
        unique=False,
    )

    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_requirement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sourcing_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="mock"),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "score",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="sourced"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["role_requirement_id"], ["role_requirements.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sourcing_run_id"], ["sourcing_runs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidates_company_id", "candidates", ["company_id"], unique=False)
    op.create_index(
        "ix_candidates_role_requirement_id",
        "candidates",
        ["role_requirement_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidates_sourcing_run_id", "candidates", ["sourcing_run_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_candidates_sourcing_run_id", table_name="candidates")
    op.drop_index("ix_candidates_role_requirement_id", table_name="candidates")
    op.drop_index("ix_candidates_company_id", table_name="candidates")
    op.drop_table("candidates")
    op.drop_index("ix_sourcing_runs_role_requirement_id", table_name="sourcing_runs")
    op.drop_index("ix_sourcing_runs_company_id", table_name="sourcing_runs")
    op.drop_table("sourcing_runs")
