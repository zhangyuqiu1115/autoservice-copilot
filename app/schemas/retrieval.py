from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class RetrievalRequest(BaseModel):
    """语义检索请求。"""

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
    def normalize_query(
        cls,
        value: str,
    ) -> str:
        """去除问题两端空白并拒绝空问题。"""

        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError(
                "Search query must not be blank."
            )

        return cleaned_value


class RetrievedChunkResponse(BaseModel):
    """语义检索返回的文本块。"""

    model_config = ConfigDict(
        from_attributes=True
    )

    chunk_id: int
    document_id: int
    chunk_index: int
    content: str
    score: float
