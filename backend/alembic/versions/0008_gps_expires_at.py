"""Adiciona gps_expires_at ao subscribers (timeout do fluxo GPS).

Revision ID: 0008_gps_expires_at
Revises: 0007_awaiting_gps
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_gps_expires_at"
down_revision = "0007_awaiting_gps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscribers", sa.Column("gps_expires_at", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("subscribers", "gps_expires_at")