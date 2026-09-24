from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import PowertrainType


class Vehicle(Base):
    """需要售后服务的车辆。"""

    __tablename__ = "vehicles"

    __table_args__ = (
        CheckConstraint(
            "length(vin) = 17",
            name="ck_vehicles_vin_length",
        ),
        CheckConstraint(
            "model_year >= 2000 AND model_year <= 2100",
            name="ck_vehicles_model_year_range",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    vin: Mapped[str] = mapped_column(
        String(17),
        unique=True,
        index=True,
        nullable=False,
    )

    brand: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )

    model_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    powertrain_type: Mapped[PowertrainType] = mapped_column(
        Enum(
            PowertrainType,
            name="powertrain_type",
            native_enum=False,
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )