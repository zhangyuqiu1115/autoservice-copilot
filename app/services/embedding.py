from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    from fastembed import TextEmbedding


class EmbeddingServiceError(Exception):
    """Embedding 模型加载或向量生成失败。"""


@lru_cache
def get_embedding_model() -> TextEmbedding:
    """加载并缓存 Embedding 模型实例。"""

    settings = get_settings()
    cache_directory = Path(
        settings.embedding_cache_directory
    )
    cache_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        from fastembed import TextEmbedding

        return TextEmbedding(
            model_name=settings.embedding_model_name,
            cache_dir=str(cache_directory),
        )
    except Exception as error:
        raise EmbeddingServiceError(
            "Could not load the embedding model."
        ) from error


def embed_texts(
    texts: Sequence[str],
) -> list[list[float]]:
    """将一组非空文本转换为向量。"""

    if not texts:
        return []

    cleaned_texts: list[str] = []

    for text in texts:
        cleaned_text = text.strip()

        if not cleaned_text:
            raise EmbeddingServiceError(
                "Embedding text must not be empty."
            )

        cleaned_texts.append(cleaned_text)

    try:
        embeddings = get_embedding_model().embed(
            cleaned_texts
        )

        return [
            embedding.tolist()
            for embedding in embeddings
        ]
    except EmbeddingServiceError:
        raise
    except Exception as error:
        raise EmbeddingServiceError(
            "Could not generate text embeddings."
        ) from error


def embed_query(query: str) -> list[float]:
    """将单条检索问题转换为向量。"""

    return embed_texts([query])[0]


@lru_cache
def get_embedding_dimension() -> int:
    """返回当前模型生成的向量维度。"""

    return len(
        embed_query(
            "新能源汽车售后服务知识检索"
        )
    )
