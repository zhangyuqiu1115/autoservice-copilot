from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import ProcessingStatus
from app.services import (
    document as document_service,
)
from app.services import (
    vector_store as vector_store_service,
)
from app.services.document_parser import (
    extract_and_chunk_document,
)


class DocumentProcessingError(Exception):
    """文档内容处理失败。"""

    def __init__(
        self,
        document_id: int,
        message: str,
    ) -> None:
        self.document_id = document_id
        self.message = message

        super().__init__(
            f"Could not process document ID "
            f"{document_id}: {message}"
        )


def _mark_document_as_failed(
    db: Session,
    document_id: int,
    error: Exception,
) -> None:
    """记录文档处理失败状态，同时保留原始异常。"""

    failed_document = db.get(
        Document,
        document_id,
    )

    if failed_document is None:
        return

    failed_document.processing_status = (
        ProcessingStatus.FAILED
    )
    failed_document.error_message = str(error)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()


def process_document(
    db: Session,
    document_id: int,
) -> Document:
    """提取文档内容、生成文本块并写入数据库。"""

    document = document_service.get_document_by_id(
        db,
        document_id,
    )

    settings = get_settings()

    try:
        document.processing_status = (
            ProcessingStatus.PROCESSING
        )
        document.error_message = None

        db.commit()
        db.refresh(document)

        chunks = extract_and_chunk_document(
            document.source_path,
            chunk_size=(
                settings.document_chunk_size_chars
            ),
            chunk_overlap=(
                settings.document_chunk_overlap_chars
            ),
        )

        db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id
                == document_id
            )
        )

        chunk_records = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=chunk_index,
                content=chunk,
                character_count=len(chunk),
            )
            for chunk_index, chunk in enumerate(chunks)
        ]

        db.add_all(chunk_records)

        document.chunk_count = len(chunk_records)

        db.commit()
        db.refresh(document)

        vector_store_service.index_document_chunks(
            document_id,
            chunk_records,
        )

        document.processing_status = (
            ProcessingStatus.COMPLETED
        )
        document.error_message = None

        db.commit()
        db.refresh(document)
    except Exception as error:
        db.rollback()

        _mark_document_as_failed(
            db,
            document_id,
            error,
        )

        raise DocumentProcessingError(
            document_id,
            str(error),
        ) from error

    return document


def list_document_chunks(
    db: Session,
    document_id: int,
) -> list[DocumentChunk]:
    """按顺序查询指定文档的全部文本块。"""

    document_service.get_document_by_id(
        db,
        document_id,
    )

    statement = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id
            == document_id
        )
        .order_by(DocumentChunk.chunk_index)
    )

    return list(db.scalars(statement).all())