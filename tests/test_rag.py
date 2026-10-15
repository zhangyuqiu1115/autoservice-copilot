from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.services import document as document_service
from app.services import rag as rag_service
from app.services import vector_store as vector_store_service


def override_get_db() -> Generator[None, None, None]:
    """RAG API 测试不访问真实数据库。"""

    yield None


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """创建隔离的 FastAPI 测试客户端。"""

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_rag_answer_api_returns_grounded_answer(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RAG API 应规范化问题并序列化回答和引用。"""

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        document_service,
        "get_document_by_id",
        lambda db, document_id: object(),
    )

    def fake_answer(
        query: str,
        *,
        limit: int | None = None,
        document_id: int | None = None,
    ) -> rag_service.RagAnswer:
        captured.update(
            query=query,
            limit=limit,
            document_id=document_id,
        )
        return rag_service.RagAnswer(
            query=query,
            answer="充电前应确认充电口干燥。[来源 1]",
            grounded=True,
            mode="extractive",
            citations=[
                rag_service.RagCitation(
                    source_number=1,
                    chunk_id=10,
                    document_id=1,
                    chunk_index=0,
                    score=0.98,
                    excerpt="充电前请确认充电口干燥。",
                )
            ],
        )

    monkeypatch.setattr(rag_service, "answer_question", fake_answer)

    response = client.post(
        "/api/v1/rag/answer",
        json={
            "query": " 充电前需要检查什么？ ",
            "limit": 3,
            "document_id": 1,
        },
    )

    assert response.status_code == 200
    assert captured == {
        "query": "充电前需要检查什么？",
        "limit": 3,
        "document_id": 1,
    }
    assert response.json() == {
        "query": "充电前需要检查什么？",
        "answer": "充电前应确认充电口干燥。[来源 1]",
        "grounded": True,
        "mode": "extractive",
        "citations": [
            {
                "source_number": 1,
                "chunk_id": 10,
                "document_id": 1,
                "chunk_index": 0,
                "score": 0.98,
                "excerpt": "充电前请确认充电口干燥。",
            }
        ],
    }


def test_rag_answer_api_validates_request(client: TestClient) -> None:
    """空问题、非法返回数量和文档 ID 应被拒绝。"""

    blank_response = client.post(
        "/api/v1/rag/answer",
        json={"query": "   "},
    )
    invalid_limit_response = client.post(
        "/api/v1/rag/answer",
        json={"query": "charging", "limit": 0},
    )
    invalid_document_response = client.post(
        "/api/v1/rag/answer",
        json={"query": "charging", "document_id": 0},
    )

    assert blank_response.status_code == 422
    assert invalid_limit_response.status_code == 422
    assert invalid_document_response.status_code == 422


def test_rag_answer_api_handles_missing_document(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """按不存在文档过滤时应返回 404。"""

    def fail_document_lookup(db: object, document_id: int) -> None:
        raise document_service.DocumentNotFoundError(document_id)

    monkeypatch.setattr(
        document_service,
        "get_document_by_id",
        fail_document_lookup,
    )

    response = client.post(
        "/api/v1/rag/answer",
        json={"query": "charging", "document_id": 999},
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (
            vector_store_service.VectorStoreError("Vector store unavailable."),
            503,
        ),
        (
            rag_service.RagServiceError("Could not generate a RAG answer."),
            502,
        ),
    ],
)
def test_rag_answer_api_maps_service_errors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_status: int,
) -> None:
    """检索和生成错误应映射为不同的 HTTP 状态。"""

    def fail_answer(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(rag_service, "answer_question", fail_answer)

    response = client.post(
        "/api/v1/rag/answer",
        json={"query": "charging safety"},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == str(error)
