"""Add simulation_basis JSONB column to flowsheets table.

Revision ID: 004_simulation_basis
Revises: 003_flowsheet_versions
Create Date: 2026-03-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_simulation_basis"
down_revision: Union[str, None] = "003_flowsheet_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "flowsheets",
        sa.Column(
            "simulation_basis",
            postgresql.JSONB(),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("flowsheets", "simulation_basis")
