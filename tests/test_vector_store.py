from collections.abc import Iterator

import pytest
from qdrant_client import QdrantClient

from app.models.document_chunk import DocumentChunk
from app.services import vector_store
from app.services.vector_store import VectorStoreError


def make_chunk(
    *,
    chunk_id: int,
    document_id: int,
    chunk_index: int,
    content: str,
) -> DocumentChunk:
    """创建测试用文本块。"""

    return DocumentChunk(
        id=chunk_id,
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        character_count=len(content),
    )


@pytest.fixture
def qdrant_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[QdrantClient]:
    """创建使用三维向量的内存 Qdrant。"""

    monkeypatch.setattr(
        vector_store,
        "get_embedding_dimension",
        lambda: 3,
    )

    client = QdrantClient(":memory:")

    yield client

    client.close()


def test_index_and_search_document_chunks(
    qdrant_client: QdrantClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = [
        make_chunk(
            chunk_id=1,
            document_id=1,
            chunk_index=0,
            content="charging safety",
        ),
        make_chunk(
            chunk_id=2,
            document_id=1,
            chunk_index=1,
            content="service booking",
        ),
        make_chunk(
            chunk_id=3,
            document_id=2,
            chunk_index=0,
            content="battery charging",
        ),
    ]
    text_vectors = {
        "charging safety": [1.0, 0.0, 0.0],
        "service booking": [0.0, 1.0, 0.0],
        "battery charging": [0.9, 0.1, 0.0],
    }

    monkeypatch.setattr(
        vector_store,
        "embed_texts",
        lambda texts: [
            text_vectors[text]
            for text in texts
        ],
    )

    assert (
        vector_store.index_document_chunks(
            1,
            chunks[:2],
            qdrant_client,
        )
        == 2
    )
    assert (
        vector_store.index_document_chunks(
            2,
            chunks[2:],
            qdrant_client,
        )
        == 1
    )

    monkeypatch.setattr(
        vector_store,
        "embed_query",
        lambda query: [1.0, 0.0, 0.0],
    )

    results = vector_store.search_document_chunks(
        "charging question",
        limit=3,
        client=qdrant_client,
    )

    assert len(results) == 3
    assert results[0].chunk_id == 1
    assert results[0].content == "charging safety"
    assert results[0].score == pytest.approx(1.0)

    filtered_results = (
        vector_store.search_document_chunks(
            "charging question",
            limit=3,
            document_id=1,
            client=qdrant_client,
        )
    )

    assert [
        result.chunk_id
        for result in filtered_results
    ] == [1, 2]
    assert all(
        result.document_id == 1
        for result in filtered_results
    )


def test_reindex_replaces_old_document_vectors(
    qdrant_client: QdrantClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_chunks = [
        make_chunk(
            chunk_id=10,
            document_id=5,
            chunk_index=0,
            content="old first chunk",
        ),
        make_chunk(
            chunk_id=11,
            document_id=5,
            chunk_index=1,
            content="old second chunk",
        ),
    ]
    new_chunk = make_chunk(
        chunk_id=12,
        document_id=5,
        chunk_index=0,
        content="new replacement chunk",
    )
    text_vectors = {
        "old first chunk": [1.0, 0.0, 0.0],
        "old second chunk": [0.0, 1.0, 0.0],
        "new replacement chunk": [1.0, 0.0, 0.0],
    }

    monkeypatch.setattr(
        vector_store,
        "embed_texts",
        lambda texts: [
            text_vectors[text]
            for text in texts
        ],
    )
    monkeypatch.setattr(
        vector_store,
        "embed_query",
        lambda query: [1.0, 0.0, 0.0],
    )

    vector_store.index_document_chunks(
        5,
        old_chunks,
        qdrant_client,
    )
    vector_store.index_document_chunks(
        5,
        [new_chunk],
        qdrant_client,
    )

    results = vector_store.search_document_chunks(
        "replacement",
        limit=10,
        document_id=5,
        client=qdrant_client,
    )

    assert [
        result.chunk_id
        for result in results
    ] == [12]


def test_empty_index_removes_document_vectors(
    qdrant_client: QdrantClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = make_chunk(
        chunk_id=20,
        document_id=8,
        chunk_index=0,
        content="temporary chunk",
    )

    monkeypatch.setattr(
        vector_store,
        "embed_texts",
        lambda texts: [[1.0, 0.0, 0.0]],
    )
    monkeypatch.setattr(
        vector_store,
        "embed_query",
        lambda query: [1.0, 0.0, 0.0],
    )

    vector_store.index_document_chunks(
        8,
        [chunk],
        qdrant_client,
    )

    assert (
        vector_store.index_document_chunks(
            8,
            [],
            qdrant_client,
        )
        == 0
    )
    assert (
        vector_store.search_document_chunks(
            "temporary",
            document_id=8,
            client=qdrant_client,
        )
        == []
    )


def test_vector_store_rejects_invalid_inputs(
    qdrant_client: QdrantClient,
) -> None:
    wrong_document_chunk = make_chunk(
        chunk_id=30,
        document_id=2,
        chunk_index=0,
        content="wrong document",
    )

    with pytest.raises(
        VectorStoreError,
        match="must belong",
    ):
        vector_store.index_document_chunks(
            1,
            [wrong_document_chunk],
            qdrant_client,
        )

    with pytest.raises(
        VectorStoreError,
        match="must not be empty",
    ):
        vector_store.search_document_chunks(
            "   ",
            client=qdrant_client,
        )

    with pytest.raises(
        VectorStoreError,
        match="at least 1",
    ):
        vector_store.search_document_chunks(
            "query",
            limit=0,
            client=qdrant_client,
        )