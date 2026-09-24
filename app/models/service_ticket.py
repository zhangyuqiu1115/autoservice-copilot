from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RiskLevel, TicketStatus
from app.models.vehicle import Vehicle


class ServiceTicket(Base):
    """记录用户问题、AI 建议和人工审核结果的售后工单。"""

    __tablename__ = "service_tickets"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    ticket_number: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )

    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey(
            "vehicles.id",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )

    customer_question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    issue_category: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        nullable=True,
    )

    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(
            RiskLevel,
            name="risk_level",
            native_enum=False,
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        default=RiskLevel.UNKNOWN,
        index=True,
        nullable=False,
    )

    risk_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[TicketStatus] = mapped_column(
        Enum(
            TicketStatus,
            name="ticket_status",
            native_enum=False,
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        default=TicketStatus.DRAFT,
        index=True,
        nullable=False,
    )

    ai_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recommended_action: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    requires_human_review: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    final_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    vehicle: Mapped[Vehicle] = relationship()
    