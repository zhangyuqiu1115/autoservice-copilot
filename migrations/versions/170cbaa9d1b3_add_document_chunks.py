"""add document chunks

Revision ID: 170cbaa9d1b3
Revises: 5cd32595cf79
Create Date: 2026-10-07 18:34:50.121728

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "170cbaa9d1b3"
down_revision: str | Sequence[str] | None = "5cd32595cf79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "document_chunks",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "chunk_index",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "character_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "character_count > 0",
            name=(
                "ck_document_chunks_"
                "character_count_positive"
            ),
        ),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name=(
                "ck_document_chunks_"
                "chunk_index_non_negative"
            ),
        ),
        sa.CheckConstraint(
            "length(trim(content)) > 0",
            name=(
                "ck_document_chunks_"
                "content_not_empty"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name=(
                "uq_document_chunks_"
                "document_id_chunk_index"
            ),
        ),
    )

    with op.batch_alter_table(
        "document_chunks",
        schema=None,
    ) as batch_op:
        batch_op.create_index(
            batch_op.f(
                "ix_document_chunks_document_id"
            ),
            ["document_id"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""

    with op.batch_alter_table(
        "document_chunks",
        schema=None,
    ) as batch_op:
        batch_op.drop_index(
            batch_op.f(
                "ix_document_chunks_document_id"
            )
        )

    op.drop_table("document_chunks")