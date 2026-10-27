"""Adiciona receive_alerts/receive_bulletins ao subscribers (inscrição modular).

Revision ID: 0005_subscription_types
Revises: 0004_admin_sessions
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_subscription_types"
down_revision = "0004_admin_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscribers",
        sa.Column("receive_alerts", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "subscribers",
        sa.Column("receive_bulletins", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # Preserva comportamento anterior.
    op.execute("UPDATE subscribers SET receive_alerts = is_active")
    op.execute("UPDATE subscribers SET receive_bulletins = is_active WHERE phone LIKE '%@g.us'")


def downgrade() -> None:
    op.drop_column("subscribers", "receive_bulletins")
    op.drop_column("subscribers", "receive_alerts")