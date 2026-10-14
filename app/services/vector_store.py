from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from qdrant_client import QdrantClient, models

from app.core.config import get_settings
from app.models.document_chunk import DocumentChunk
from app.services.embedding import (
    embed_query,
    embed_texts,
    get_embedding_dimension,
)


class VectorStoreError(Exception):
    """向量数据库操作失败。"""


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """一次向量检索返回的文本块。"""

    chunk_id: int
    document_id: int
    chunk_index: int
    content: str
    score: float


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """创建并缓存本地 Qdrant 客户端。"""

    settings = get_settings()
    qdrant_path = Path(settings.qdrant_path)
    qdrant_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        return QdrantClient(
            path=str(qdrant_path),
        )
    except Exception as error:
        raise VectorStoreError(
            "Could not initialize Qdrant."
        ) from error

def close_qdrant_client() -> None:
    """在应用关闭前释放本地 Qdrant 资源。"""

    if (
        get_qdrant_client.cache_info().currsize
        == 0
    ):
        return

    client = get_qdrant_client()
    client.close()
    get_qdrant_client.cache_clear()
def _document_filter(
    document_id: int,
) -> models.Filter:
    """创建按文档 ID 匹配的 Qdrant 过滤条件。"""

    return models.Filter(
        must=[
            models.FieldCondition(
                key="document_id",
                match=models.MatchValue(
                    value=document_id,
                ),
            )
        ]
    )


def ensure_collection(
    client: QdrantClient | None = None,
) -> QdrantClient:
    """确保文档文本块集合已经存在。"""

    settings = get_settings()
    active_client = client or get_qdrant_client()

    try:
        if not active_client.collection_exists(
            settings.qdrant_collection_name
        ):
            active_client.create_collection(
                collection_name=(
                    settings.qdrant_collection_name
                ),
                vectors_config=models.VectorParams(
                    size=get_embedding_dimension(),
                    distance=models.Distance.COSINE,
                ),
            )
    except Exception as error:
        raise VectorStoreError(
            "Could not prepare the Qdrant collection."
        ) from error

    return active_client


def delete_document_vectors(
    document_id: int,
    client: QdrantClient | None = None,
) -> None:
    """删除指定文档的全部向量。"""

    settings = get_settings()
    active_client = ensure_collection(client)

    try:
        active_client.delete(
            collection_name=(
                settings.qdrant_collection_name
            ),
            points_selector=_document_filter(
                document_id
            ),
            wait=True,
        )
    except Exception as error:
        raise VectorStoreError(
            f"Could not delete vectors for "
            f"document ID {document_id}."
        ) from error


def index_document_chunks(
    document_id: int,
    chunks: Sequence[DocumentChunk],
    client: QdrantClient | None = None,
) -> int:
    """生成并保存指定文档全部文本块的向量。"""

    stored_chunks = list(chunks)

    if any(
        chunk.document_id != document_id
        for chunk in stored_chunks
    ):
        raise VectorStoreError(
            "All chunks must belong to the requested document."
        )

    active_client = ensure_collection(client)
    settings = get_settings()

    if not stored_chunks:
        delete_document_vectors(
            document_id,
            active_client,
        )
        return 0

    try:
        vectors = embed_texts(
            [
                chunk.content
                for chunk in stored_chunks
            ]
        )

        points: list[models.PointStruct] = []

        for chunk, vector in zip(
            stored_chunks,
            vectors,
            strict=True,
        ):
            if chunk.id is None:
                raise VectorStoreError(
                    "Document chunks must be saved "
                    "before vector indexing."
                )

            points.append(
                models.PointStruct(
                    id=chunk.id,
                    vector=vector,
                    payload={
                        "chunk_id": chunk.id,
                        "document_id": (
                            chunk.document_id
                        ),
                        "chunk_index": (
                            chunk.chunk_index
                        ),
                        "content": chunk.content,
                    },
                )
            )

        active_client.delete(
            collection_name=(
                settings.qdrant_collection_name
            ),
            points_selector=_document_filter(
                document_id
            ),
            wait=True,
        )
        active_client.upsert(
            collection_name=(
                settings.qdrant_collection_name
            ),
            points=points,
            wait=True,
        )
    except VectorStoreError:
        raise
    except Exception as error:
        raise VectorStoreError(
            f"Could not index chunks for "
            f"document ID {document_id}."
        ) from error

    return len(points)


def search_document_chunks(
    query: str,
    *,
    limit: int | None = None,
    document_id: int | None = None,
    client: QdrantClient | None = None,
) -> list[RetrievedChunk]:
    """根据语义相似度检索文档文本块。"""

    cleaned_query = query.strip()

    if not cleaned_query:
        raise VectorStoreError(
            "Search query must not be empty."
        )

    settings = get_settings()
    search_limit = (
        limit
        if limit is not None
        else settings.retrieval_top_k
    )

    if search_limit < 1:
        raise VectorStoreError(
            "Search limit must be at least 1."
        )

    active_client = ensure_collection(client)

    try:
        response = active_client.query_points(
            collection_name=(
                settings.qdrant_collection_name
            ),
            query=embed_query(cleaned_query),
            query_filter=(
                _document_filter(document_id)
                if document_id is not None
                else None
            ),
            limit=search_limit,
            with_payload=True,
            with_vectors=False,
        )

        results: list[RetrievedChunk] = []

        for point in response.points:
            payload = point.payload or {}

            results.append(
                RetrievedChunk(
                    chunk_id=int(
                        payload["chunk_id"]
                    ),
                    document_id=int(
                        payload["document_id"]
                    ),
                    chunk_index=int(
                        payload["chunk_index"]
                    ),
                    content=str(
                        payload["content"]
                    ),
                    score=float(point.score),
                )
            )
    except Exception as error:
        raise VectorStoreError(
            "Could not search document chunks."
        ) from error

    return results
