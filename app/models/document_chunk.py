from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentChunk(Base):
    """从知识库文档中提取的可检索文本块。"""

    __tablename__ = "document_chunks"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name=(
                "uq_document_chunks_"
                "document_id_chunk_index"
            ),
        ),
        CheckConstraint(
            "chunk_index >= 0",
            name=(
                "ck_document_chunks_"
                "chunk_index_non_negative"
            ),
        ),
        CheckConstraint(
            "character_count > 0",
            name=(
                "ck_document_chunks_"
                "character_count_positive"
            ),
        ),
        CheckConstraint(
            "length(trim(content)) > 0",
            name=(
                "ck_document_chunks_"
                "content_not_empty"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )