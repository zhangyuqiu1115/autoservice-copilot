from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import DocumentType, ProcessingStatus


class DocumentUploadMetadata(BaseModel):
    """上传知识库文档时附带的业务信息。"""

    title: str = Field(
        min_length=1,
        max_length=200,
        examples=["BYD Han EV Owner Manual"],
    )

    document_type: DocumentType

    vehicle_brand: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        examples=["BYD"],
    )

    vehicle_model: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        examples=["Han EV"],
    )

    model_year: int | None = Field(
        default=None,
        ge=2000,
        le=2100,
        examples=[2025],
    )

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: object) -> object:
        """删除文档标题两端的空格。"""

        if isinstance(value, str):
            return value.strip()

        return value

    @field_validator(
        "vehicle_brand",
        "vehicle_model",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        """清理可选文本，并把空字符串转换为 None。"""

        if isinstance(value, str):
            stripped_value = value.strip()
            return stripped_value or None

        return value


class DocumentResponse(BaseModel):
    """返回给 API 客户端的文档元数据。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    document_type: DocumentType
    source_filename: str
    vehicle_brand: str | None
    vehicle_model: str | None
    model_year: int | None
    checksum: str
    processing_status: ProcessingStatus
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime