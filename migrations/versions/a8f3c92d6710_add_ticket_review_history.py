"""Add ticket version and append-only review history.

Revision ID: a8f3c92d6710
Revises: 170cbaa9d1b3
"""

import sqlalchemy as sa
from alembic import op

revision = "a8f3c92d6710"
down_revision = "170cbaa9d1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_tickets",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("ticket_version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=False),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("reviewer", sa.String(100), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("final_response", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["service_tickets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", "ticket_version", name="uq_ticket_events_version"),
    )
    op.create_index("ix_ticket_events_ticket_id", "ticket_events", ["ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_events_ticket_id", table_name="ticket_events")
    op.drop_table("ticket_events")
    with op.batch_alter_table("service_tickets") as batch_op:
        batch_op.drop_column("version")
