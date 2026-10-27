"""Adiciona bulletin_time ao subscribers (boletins personalizados por grupo).

Revision ID: 0006_bulletin_time
Revises: 0005_subscription_types
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_bulletin_time"
down_revision = "0005_subscription_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscribers", sa.Column("bulletin_time", sa.String(5), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("subscribers", "bulletin_time")