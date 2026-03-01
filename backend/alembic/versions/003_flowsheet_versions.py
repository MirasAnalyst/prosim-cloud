"""Add flowsheet_versions table for project versioning.

Revision ID: 003_flowsheet_versions
Revises: 002_chat_messages
Create Date: 2026-03-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_flowsheet_versions"
down_revision: Union[str, None] = "002_chat_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flowsheet_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "flowsheet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flowsheets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("nodes", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("edges", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("property_package", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("flowsheet_id", "version_number", name="uq_flowsheet_version"),
    )
    op.create_index("ix_flowsheet_versions_flowsheet_id", "flowsheet_versions", ["flowsheet_id"])


def downgrade() -> None:
    op.drop_index("ix_flowsheet_versions_flowsheet_id", table_name="flowsheet_versions")
    op.drop_table("flowsheet_versions")
