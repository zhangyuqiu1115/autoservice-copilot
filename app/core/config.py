from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AutoService Copilot API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"

    database_url: str = "sqlite:///./autoservice.db"

    upload_directory: str = "data/uploads"
    max_upload_size_mb: int = 10

    document_chunk_size_chars: int = Field(
        default=1000,
        ge=100,
    )
    document_chunk_overlap_chars: int = Field(
        default=200,
        ge=0,
    )

    qdrant_path: str = "data/qdrant"
    qdrant_collection_name: str = "document_chunks"
    embedding_model_name: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    embedding_cache_directory: str = "data/models"
    retrieval_top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_document_chunk_settings(self) -> Self:
        """确保分块重叠长度小于分块长度。"""

        if (
            self.document_chunk_overlap_chars
            >= self.document_chunk_size_chars
        ):
            raise ValueError(
                "DOCUMENT_CHUNK_OVERLAP_CHARS must be smaller "
                "than DOCUMENT_CHUNK_SIZE_CHARS."
            )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
