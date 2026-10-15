from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RagAnswerRequest(BaseModel):
    """基于已索引售后文档回答问题。"""

    query: str = Field(
        min_length=1,
        max_length=1000,
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=20,
    )
    document_id: int | None = Field(
        default=None,
        ge=1,
    )

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        """去除问题两端空白并拒绝空问题。"""

        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("Question must not be blank.")

        return cleaned_value


class RagCitationResponse(BaseModel):
    """回答引用的文档文本块。"""

    model_config = ConfigDict(from_attributes=True)

    source_number: int
    chunk_id: int
    document_id: int
    chunk_index: int
    score: float
    excerpt: str


class RagAnswerResponse(BaseModel):
    """有依据的 RAG 回答或无证据拒答。"""

    model_config = ConfigDict(from_attributes=True)

    query: str
    answer: str
    grounded: bool
    mode: Literal["extractive", "openai_compatible", "no_evidence"]
    citations: list[RagCitationResponse]
