from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

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

DOCUMENT_CONTENT = (
    b"BYD Han EV battery safety and charging instructions."
)

DOCUMENT_FORM_DATA = {
    "title": "BYD Han EV Owner Manual",
    "document_type": "owner_manual",
    "vehicle_brand": "BYD",
    "vehicle_model": "Han EV",
    "model_year": "2025",
}


@event.listens_for(test_engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection: Any,
    _connection_record: Any,
) -> None:
    """在测试数据库中启用外键约束。"""

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def override_get_db() -> Generator[Session, None, None]:
    """使用测试数据库替代真实数据库。"""

    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    """为每个测试创建独立数据库和上传目录。"""

    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db

    settings = get_settings()
    monkeypatch.setattr(
        settings,
        "upload_directory",
        str(tmp_path / "uploads"),
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_document_upload_lifecycle(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """测试上传、列表、详情、重复检查和不存在文档。"""

    files = {
        "file": (
            "han-ev-owner-manual.txt",
            DOCUMENT_CONTENT,
            "text/plain",
        )
    }

    create_response = client.post(
        "/api/v1/documents",
        data=DOCUMENT_FORM_DATA,
        files=files,
    )

    assert create_response.status_code == 201

    created_document = create_response.json()
    document_id = created_document["id"]

    assert created_document["title"] == DOCUMENT_FORM_DATA["title"]
    assert created_document["document_type"] == "owner_manual"
    assert created_document["source_filename"] == (
        "han-ev-owner-manual.txt"
    )
    assert created_document["processing_status"] == "pending"
    assert created_document["chunk_count"] == 0
    assert len(created_document["checksum"]) == 64

    stored_files = list(
        (tmp_path / "uploads").glob("*.txt")
    )

    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == DOCUMENT_CONTENT

    list_response = client.get("/api/v1/documents")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == document_id

    get_response = client.get(
        f"/api/v1/documents/{document_id}",
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == document_id

    duplicate_response = client.post(
        "/api/v1/documents",
        data=DOCUMENT_FORM_DATA,
        files={
            "file": (
                "duplicate.txt",
                DOCUMENT_CONTENT,
                "text/plain",
            )
        },
    )

    assert duplicate_response.status_code == 409

    missing_response = client.get(
        "/api/v1/documents/999999",
    )

    assert missing_response.status_code == 404


def test_document_upload_rejects_invalid_files(
    client: TestClient,
) -> None:
    """测试不支持的扩展名、错误 MIME 类型和空文件。"""

    unsupported_response = client.post(
        "/api/v1/documents",
        data=DOCUMENT_FORM_DATA,
        files={
            "file": (
                "malware.exe",
                b"not allowed",
                "application/octet-stream",
            )
        },
    )

    assert unsupported_response.status_code == 415

    invalid_content_type_response = client.post(
        "/api/v1/documents",
        data=DOCUMENT_FORM_DATA,
        files={
            "file": (
                "manual.pdf",
                b"not a pdf",
                "text/plain",
            )
        },
    )

    assert invalid_content_type_response.status_code == 415

    empty_response = client.post(
        "/api/v1/documents",
        data=DOCUMENT_FORM_DATA,
        files={
            "file": (
                "empty.txt",
                b"",
                "text/plain",
            )
        },
    )

    assert empty_response.status_code == 400

def test_document_processing_api(
    client: TestClient,
) -> None:
    """测试上传、处理和查询 chunks 的完整 API 流程。"""

    upload_response = client.post(
        "/api/v1/documents",
        data=DOCUMENT_FORM_DATA,
        files={
            "file": (
                "processing-test.txt",
                DOCUMENT_CONTENT,
                "text/plain",
            )
        },
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]

    process_response = client.post(
        f"/api/v1/documents/{document_id}/process",
    )

    assert process_response.status_code == 200

    processed_document = process_response.json()

    assert processed_document["processing_status"] == (
        "completed"
    )
    assert processed_document["chunk_count"] == 1
    assert processed_document["error_message"] is None

    chunks_response = client.get(
        f"/api/v1/documents/{document_id}/chunks",
    )

    assert chunks_response.status_code == 200

    chunks = chunks_response.json()

    assert len(chunks) == 1
    assert chunks[0]["document_id"] == document_id
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["content"] == (
        DOCUMENT_CONTENT.decode("utf-8")
    )
    assert chunks[0]["character_count"] == len(
        chunks[0]["content"]
    )

    missing_process_response = client.post(
        "/api/v1/documents/999999/process",
    )

    missing_chunks_response = client.get(
        "/api/v1/documents/999999/chunks",
    )

    assert missing_process_response.status_code == 404
    assert missing_chunks_response.status_code == 404