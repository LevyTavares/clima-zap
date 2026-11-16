"""Adiciona window_minutes ao subscribers (janela da previsão on-demand).

Revision ID: 0009_forecast_window
Revises: 0008_gps_expires_at
Create Date: 2026-11-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_forecast_window"
down_revision = "0008_gps_expires_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscribers", sa.Column("window_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("subscribers", "window_minutes")
