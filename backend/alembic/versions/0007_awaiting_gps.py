"""Adiciona awaiting_gps ao subscribers (fluxo de localização por GPS).

Revision ID: 0007_awaiting_gps
Revises: 0006_bulletin_time
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_awaiting_gps"
down_revision = "0006_bulletin_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscribers",
        sa.Column("awaiting_gps", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("subscribers", "awaiting_gps")