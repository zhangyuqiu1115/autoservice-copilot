from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.services import (
    document as document_service,
)
from app.services import (
    vector_store as vector_store_service,
)
from app.services.vector_store import RetrievedChunk


def override_get_db() -> Generator[None, None, None]:
    """检索 API 测试不访问真实数据库。"""

    yield None


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """创建隔离的 FastAPI 测试客户端。"""

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_retrieval_search_api(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """检索 API 应规范化问题并返回相关文本块。"""

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        document_service,
        "get_document_by_id",
        lambda db, document_id: object(),
    )

    def fake_search_document_chunks(
        query: str,
        *,
        limit: int | None = None,
        document_id: int | None = None,
    ) -> list[RetrievedChunk]:
        captured["query"] = query
        captured["limit"] = limit
        captured["document_id"] = document_id

        return [
            RetrievedChunk(
                chunk_id=10,
                document_id=1,
                chunk_index=0,
                content="Charging safety instructions.",
                score=0.98,
            )
        ]

    monkeypatch.setattr(
        vector_store_service,
        "search_document_chunks",
        fake_search_document_chunks,
    )

    response = client.post(
        "/api/v1/retrieval/search",
        json={
            "query": " charging safety ",
            "limit": 2,
            "document_id": 1,
        },
    )

    assert response.status_code == 200
    assert captured == {
        "query": "charging safety",
        "limit": 2,
        "document_id": 1,
    }
    assert response.json() == [
        {
            "chunk_id": 10,
            "document_id": 1,
            "chunk_index": 0,
            "content": "Charging safety instructions.",
            "score": 0.98,
        }
    ]


def test_retrieval_search_validates_request(
    client: TestClient,
) -> None:
    """空问题和非法返回数量应被拒绝。"""

    blank_response = client.post(
        "/api/v1/retrieval/search",
        json={"query": "   "},
    )
    invalid_limit_response = client.post(
        "/api/v1/retrieval/search",
        json={
            "query": "charging",
            "limit": 0,
        },
    )

    assert blank_response.status_code == 422
    assert invalid_limit_response.status_code == 422


def test_retrieval_search_handles_vector_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """向量数据库错误应转换为 503 响应。"""

    def fail_search(
        query: str,
        *,
        limit: int | None = None,
        document_id: int | None = None,
    ) -> list[RetrievedChunk]:
        raise vector_store_service.VectorStoreError(
            "Vector store unavailable."
        )

    monkeypatch.setattr(
        vector_store_service,
        "search_document_chunks",
        fail_search,
    )

    response = client.post(
        "/api/v1/retrieval/search",
        json={"query": "charging safety"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Vector store unavailable."
    )
