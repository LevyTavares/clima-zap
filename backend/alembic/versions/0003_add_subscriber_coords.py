"""Adiciona latitude/longitude ao subscribers (localização arbitrária).

Revision ID: 0003_add_coords
Revises: 0002_add_city
Create Date: 2026-10-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_add_coords"
down_revision = "0002_add_city"
branch_labels = None
depends_on = None


def upgrade() -> None:
    getattr(op, "add_column")(
        "subscribers", sa.Column("latitude", sa.Float(), nullable=True)
    )
    getattr(op, "add_column")(
        "subscribers", sa.Column("longitude", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    getattr(op, "drop_column")("subscribers", "longitude")
    getattr(op, "drop_column")("subscribers", "latitude")
