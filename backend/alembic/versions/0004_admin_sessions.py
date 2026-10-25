"""Adiciona as sessões administrativas de 7 dias (/admin register).

Revision ID: 0004_admin_sessions
Revises: 0003_add_coords
Create Date: 2026-10-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_admin_sessions"
down_revision = "0003_add_coords"
branch_labels = None
depends_on = None


def upgrade() -> None:
    getattr(op, "create_table")(
        "admin_sessions",
        sa.Column("phone", sa.String(length=64), primary_key=True),
        sa.Column("password_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("registered_at", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.Column("notified_at", sa.Float(), nullable=True),
    )
    getattr(op, "create_index")(
        "ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"]
    )


def downgrade() -> None:
    getattr(op, "drop_index")(
        "ix_admin_sessions_expires_at", table_name="admin_sessions"
    )
    getattr(op, "drop_table")("admin_sessions")
