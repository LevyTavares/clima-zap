"""Create subscriber and alert log tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    getattr(op, "create_table")(
        "subscribers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column(
            "registered_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    getattr(op, "create_index")("ix_subscribers_phone", "subscribers", ["phone"], unique=True)

    getattr(op, "create_table")(
        "alert_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "sent_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.Column("recipient", sa.String(length=128), nullable=False),
        sa.Column(
            "subscriber_id",
            sa.Integer(),
            sa.ForeignKey("subscribers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    getattr(op, "create_index")("ix_alert_logs_alert_type", "alert_logs", ["alert_type"], unique=False)


def downgrade() -> None:
    getattr(op, "drop_index")("ix_alert_logs_alert_type", table_name="alert_logs")
    getattr(op, "drop_table")("alert_logs")
    getattr(op, "drop_index")("ix_subscribers_phone", table_name="subscribers")
    getattr(op, "drop_table")("subscribers")