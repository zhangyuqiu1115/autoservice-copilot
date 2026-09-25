from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import PowertrainType


class VehicleBase(BaseModel):
    """车辆共有字段。"""

    brand: str = Field(
        min_length=1,
        max_length=50,
        examples=["BYD"],
    )

    model: str = Field(
        min_length=1,
        max_length=100,
        examples=["Han EV"],
    )

    model_year: int = Field(
        ge=2000,
        le=2100,
        examples=[2025],
    )

    powertrain_type: PowertrainType

    @field_validator("brand", "model", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        """删除品牌和车型名称两端的空格。"""

        if isinstance(value, str):
            return value.strip()

        return value


class VehicleCreate(VehicleBase):
    """创建车辆时客户端需要提供的数据。"""

    vin: str = Field(
        min_length=17,
        max_length=17,
        pattern=r"^[A-HJ-NPR-Z0-9]{17}$",
        examples=["LHGCM82633A004352"],
    )

    @field_validator("vin", mode="before")
    @classmethod
    def normalize_vin(cls, value: object) -> object:
        """删除 VIN 两端空格并转换为大写。"""

        if isinstance(value, str):
            return value.strip().upper()

        return value


class VehicleUpdate(BaseModel):
    """更新车辆时允许修改的数据。"""

    brand: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    model: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    model_year: int | None = Field(
        default=None,
        ge=2000,
        le=2100,
    )

    powertrain_type: PowertrainType | None = None

    @field_validator("brand", "model", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        """删除可选文本字段两端的空格。"""

        if isinstance(value, str):
            return value.strip()

        return value


class VehicleResponse(VehicleBase):
    """返回给 API 客户端的车辆数据。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    vin: str
    created_at: datetime
    updated_at: datetime