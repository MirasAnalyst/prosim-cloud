"""Add simulation_cases table for case study management.

Revision ID: 005_simulation_cases
Revises: 004_simulation_basis
Create Date: 2026-03-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005_simulation_cases"
down_revision: Union[str, None] = "004_simulation_basis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("nodes", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("edges", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("simulation_basis", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("property_package", sa.String(50), server_default="PengRobinson", nullable=False),
        sa.Column("results", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_simulation_cases_project_id", "simulation_cases", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_simulation_cases_project_id", table_name="simulation_cases")
    op.drop_table("simulation_cases")
