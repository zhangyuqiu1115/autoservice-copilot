import numpy as np
import pytest

from app.services import embedding as embedding_service
from app.services.embedding import EmbeddingServiceError


class FakeEmbeddingModel:
    """测试用的可控 Embedding 模型。"""

    def __init__(
        self,
        vectors: list[list[float]],
    ) -> None:
        self.vectors = vectors
        self.received_texts: list[str] = []

    def embed(
        self,
        texts: list[str],
    ):
        self.received_texts = list(texts)

        return iter(
            np.array(
                vector,
                dtype=np.float32,
            )
            for vector in self.vectors
        )


def test_embed_texts_trims_and_converts_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_model = FakeEmbeddingModel(
        [
            [0.1, 0.2],
            [0.3, 0.4],
        ]
    )
    monkeypatch.setattr(
        embedding_service,
        "get_embedding_model",
        lambda: fake_model,
    )

    result = embedding_service.embed_texts(
        [
            " first text ",
            "second text",
        ]
    )

    assert fake_model.received_texts == [
        "first text",
        "second text",
    ]
    assert result[0] == pytest.approx(
        [0.1, 0.2]
    )
    assert result[1] == pytest.approx(
        [0.3, 0.4]
    )


def test_embed_texts_returns_empty_without_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        embedding_service,
        "get_embedding_model",
        lambda: pytest.fail(
            "The model should not be loaded."
        ),
    )

    assert embedding_service.embed_texts([]) == []


def test_embed_texts_rejects_blank_text() -> None:
    with pytest.raises(
        EmbeddingServiceError,
        match="must not be empty",
    ):
        embedding_service.embed_texts(["   "])


def test_embed_query_returns_single_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_model = FakeEmbeddingModel(
        [[0.5, 0.6, 0.7]]
    )
    monkeypatch.setattr(
        embedding_service,
        "get_embedding_model",
        lambda: fake_model,
    )

    result = embedding_service.embed_query(
        " charging safety "
    )

    assert fake_model.received_texts == [
        "charging safety"
    ]
    assert result == pytest.approx(
        [0.5, 0.6, 0.7]
    )


def test_embedding_errors_are_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingEmbeddingModel:
        def embed(
            self,
            texts: list[str],
        ):
            raise RuntimeError("model failure")

    monkeypatch.setattr(
        embedding_service,
        "get_embedding_model",
        lambda: FailingEmbeddingModel(),
    )

    with pytest.raises(
        EmbeddingServiceError,
        match="Could not generate",
    ):
        embedding_service.embed_texts(["test"])