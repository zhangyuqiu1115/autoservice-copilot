from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.models.document import Document
from app.models.enums import (
    DocumentType,
    ProcessingStatus,
)
from app.services import (
    document as document_service,
)
from app.services import (
    vector_store as vector_store_service,
)
from app.services.document_processing import (
    DocumentProcessingError,
    list_document_chunks,
    process_document,
)

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
)


@event.listens_for(test_engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection: Any,
    _connection_record: Any,
) -> None:
    """在测试数据库中启用外键约束。"""

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def db(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Session, None, None]:
    """为每个测试创建独立数据库和分块配置。"""

    Base.metadata.create_all(bind=test_engine)

    settings = get_settings()
    monkeypatch.setattr(
        settings,
        "document_chunk_size_chars",
        100,
    )
    monkeypatch.setattr(
        settings,
        "document_chunk_overlap_chars",
        20,
    )
    monkeypatch.setattr(
        vector_store_service,
        "index_document_chunks",
        lambda document_id, chunks: len(chunks),
    )

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


def create_document_record(
    db: Session,
    file_path: Path,
    checksum: str,
) -> Document:
    """创建指向测试文件的文档元数据。"""

    document = Document(
        title="Test Owner Manual",
        document_type=DocumentType.OWNER_MANUAL,
        source_filename=file_path.name,
        source_path=file_path.as_posix(),
        vehicle_brand="BYD",
        vehicle_model="Han EV",
        model_year=2025,
        checksum=checksum,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def test_process_document_creates_chunks(
    db: Session,
    tmp_path: Path,
) -> None:
    """测试文档处理、分块保存和重复处理。"""

    document_path = tmp_path / "manual.txt"
    document_path.write_text(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 20,
        encoding="utf-8",
    )

    document = create_document_record(
        db,
        document_path,
        checksum="a" * 64,
    )

    processed_document = process_document(
        db,
        document.id,
    )

    chunks = list_document_chunks(
        db,
        document.id,
    )

    assert processed_document.processing_status == (
        ProcessingStatus.COMPLETED
    )
    assert processed_document.chunk_count == 7
    assert processed_document.error_message is None

    assert len(chunks) == 7
    assert [chunk.chunk_index for chunk in chunks] == (
        list(range(7))
    )
    assert all(
        chunk.character_count == len(chunk.content)
        for chunk in chunks
    )
    assert chunks[0].content[-20:] == (
        chunks[1].content[:20]
    )

    process_document(
        db,
        document.id,
    )

    reprocessed_chunks = list_document_chunks(
        db,
        document.id,
    )

    assert len(reprocessed_chunks) == 7


def test_process_document_records_failure(
    db: Session,
    tmp_path: Path,
) -> None:
    """空文档处理失败时记录 failed 状态。"""

    document_path = tmp_path / "empty.txt"
    document_path.write_text(
        "\n\t  \n",
        encoding="utf-8",
    )

    document = create_document_record(
        db,
        document_path,
        checksum="b" * 64,
    )

    with pytest.raises(
        DocumentProcessingError,
        match="Could not process document ID",
    ):
        process_document(
            db,
            document.id,
        )

    db.expire_all()

    failed_document = db.get(
        Document,
        document.id,
    )

    assert failed_document is not None
    assert failed_document.processing_status == (
        ProcessingStatus.FAILED
    )
    assert failed_document.chunk_count == 0
    assert failed_document.error_message is not None
    assert "does not contain extractable text" in (
        failed_document.error_message
    )


def test_process_document_rejects_missing_document(
    db: Session,
) -> None:
    """不存在的文档 ID 应返回领域异常。"""

    with pytest.raises(
        document_service.DocumentNotFoundError,
        match="Document with ID 999999 was not found",
    ):
        process_document(
            db,
            999999,
        )
        