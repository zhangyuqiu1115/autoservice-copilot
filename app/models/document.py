from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DocumentType, ProcessingStatus


class Document(Base):
    """进入 RAG 知识库的售后文档元数据。"""

    __tablename__ = "documents"

    __table_args__ = (
        CheckConstraint(
            "length(checksum) = 64",
            name="ck_documents_checksum_length",
        ),
        CheckConstraint(
            "chunk_count >= 0",
            name="ck_documents_chunk_count_non_negative",
        ),
        CheckConstraint(
            """
            model_year IS NULL
            OR (model_year >= 2000 AND model_year <= 2100)
            """,
            name="ck_documents_model_year_range",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    document_type: Mapped[DocumentType] = mapped_column(
        Enum(
            DocumentType,
            name="document_type",
            native_enum=False,
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        index=True,
        nullable=False,
    )

    source_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    vehicle_brand: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    vehicle_model: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        nullable=True,
    )

    model_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    checksum: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )

    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(
            ProcessingStatus,
            name="processing_status",
            native_enum=False,
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        default=ProcessingStatus.PENDING,
        index=True,
        nullable=False,
    )

    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )