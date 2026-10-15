"""Add city column to subscribers.

Revision ID: 0002_add_city
Revises: 0001_initial
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_city"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    getattr(op, "add_column")(
        "subscribers", sa.Column("city", sa.String(length=64), nullable=True)
    )


def downgrade() -> None:
    getattr(op, "drop_column")("subscribers", "city")
