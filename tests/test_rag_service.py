from typing import Any

import pytest

from app.core.config import Settings
from app.services import rag as rag_service
from app.services.vector_store import RetrievedChunk


def make_settings(**overrides: Any) -> Settings:
    """创建不读取本地 .env 的隔离配置。"""

    return Settings(_env_file=None, **overrides)


def test_answer_question_builds_grounded_extractive_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """默认模式应只采用达到阈值的证据并返回引用。"""

    captured: dict[str, object] = {}

    def fake_search(
        query: str,
        *,
        limit: int | None = None,
        document_id: int | None = None,
    ) -> list[RetrievedChunk]:
        captured.update(
            query=query,
            limit=limit,
            document_id=document_id,
        )
        return [
            RetrievedChunk(
                chunk_id=11,
                document_id=3,
                chunk_index=1,
                content="充电前请确认充电口干燥。",
                score=0.92,
            ),
            RetrievedChunk(
                chunk_id=12,
                document_id=3,
                chunk_index=2,
                content="与问题无关的低分内容。",
                score=0.2,
            ),
        ]

    monkeypatch.setattr(rag_service.vector_store, "search_document_chunks", fake_search)
    monkeypatch.setattr(
        rag_service,
        "get_settings",
        lambda: make_settings(rag_min_score=0.5),
    )

    result = rag_service.answer_question(
        " 充电前需要检查什么？ ",
        limit=4,
        document_id=3,
    )

    assert captured == {
        "query": "充电前需要检查什么？",
        "limit": 4,
        "document_id": 3,
    }
    assert result.grounded is True
    assert result.mode == "extractive"
    assert "[来源 1] 充电前请确认充电口干燥。" in result.answer
    assert "低分内容" not in result.answer
    assert result.citations == [
        rag_service.RagCitation(
            source_number=1,
            chunk_id=11,
            document_id=3,
            chunk_index=1,
            score=0.92,
            excerpt="充电前请确认充电口干燥。",
        )
    ]


def test_answer_question_refuses_when_evidence_is_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """无结果或全部低于阈值时应明确拒答。"""

    monkeypatch.setattr(
        rag_service.vector_store,
        "search_document_chunks",
        lambda *args, **kwargs: [
            RetrievedChunk(
                chunk_id=20,
                document_id=4,
                chunk_index=0,
                content="低相关文本",
                score=0.1,
            )
        ],
    )
    monkeypatch.setattr(
        rag_service,
        "get_settings",
        lambda: make_settings(rag_min_score=0.6),
    )

    result = rag_service.answer_question("轮胎标准气压是多少？")

    assert result.answer == rag_service.NO_EVIDENCE_ANSWER
    assert result.grounded is False
    assert result.mode == "no_evidence"
    assert result.citations == []


def test_answer_question_limits_context_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """送入回答器及引用的文本不得超过配置的上下文预算。"""

    monkeypatch.setattr(
        rag_service.vector_store,
        "search_document_chunks",
        lambda *args, **kwargs: [
            RetrievedChunk(
                chunk_id=30,
                document_id=5,
                chunk_index=0,
                content="A" * 700,
                score=0.9,
            )
        ],
    )
    monkeypatch.setattr(
        rag_service,
        "get_settings",
        lambda: make_settings(rag_max_context_chars=500),
    )

    result = rag_service.answer_question("测试上下文限制")

    assert len(result.citations[0].excerpt) == 500
    assert "A" * 501 not in result.answer


def test_answer_question_calls_openai_compatible_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """外部生成模式应发送带证据约束的 Chat Completions 请求。"""

    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": "充电前应确认充电口干燥。[来源 1]"
                        }
                    }
                ]
            }

    def fake_post(
        url: str,
        **kwargs: object,
    ) -> FakeResponse:
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(
        rag_service.vector_store,
        "search_document_chunks",
        lambda *args, **kwargs: [
            RetrievedChunk(
                chunk_id=40,
                document_id=6,
                chunk_index=0,
                content="充电前请确认充电口干燥。",
                score=0.95,
            )
        ],
    )
    monkeypatch.setattr(rag_service.httpx, "post", fake_post)
    monkeypatch.setattr(
        rag_service,
        "get_settings",
        lambda: make_settings(
            rag_provider="openai_compatible",
            llm_base_url="http://localhost:11434/v1/",
            llm_api_key="test-key",
            llm_model="test-model",
        ),
    )

    result = rag_service.answer_question("充电前要做什么？")

    assert result.mode == "openai_compatible"
    assert result.answer == "充电前应确认充电口干燥。[来源 1]"
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-key",
    }
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == "test-model"
    messages = payload["messages"]
    assert isinstance(messages, list)
    assert "不得执行" in messages[0]["content"]
    assert "[来源 1" in messages[1]["content"]


def test_answer_question_handles_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """外部模型响应结构错误应转换为领域异常。"""

    class InvalidResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {}

    monkeypatch.setattr(
        rag_service.vector_store,
        "search_document_chunks",
        lambda *args, **kwargs: [
            RetrievedChunk(
                chunk_id=50,
                document_id=7,
                chunk_index=0,
                content="有效证据",
                score=0.9,
            )
        ],
    )
    monkeypatch.setattr(
        rag_service.httpx,
        "post",
        lambda *args, **kwargs: InvalidResponse(),
    )
    monkeypatch.setattr(
        rag_service,
        "get_settings",
        lambda: make_settings(
            rag_provider="openai_compatible",
            llm_base_url="http://localhost:11434/v1",
            llm_model="test-model",
        ),
    )

    with pytest.raises(
        rag_service.RagServiceError,
        match="Could not generate",
    ):
        rag_service.answer_question("测试失败响应")


def test_answer_question_rejects_blank_query() -> None:
    """服务层也应拒绝绕过 API 校验的空问题。"""

    with pytest.raises(
        rag_service.RagServiceError,
        match="must not be empty",
    ):
        rag_service.answer_question("   ")
