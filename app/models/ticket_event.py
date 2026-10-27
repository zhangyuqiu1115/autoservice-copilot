from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TicketEvent(Base):
    """审核事件只追加；同一工单版本最多有一条状态变更记录。"""

    __tablename__ = "ticket_events"
    __table_args__ = (
        UniqueConstraint("ticket_id", "ticket_version", name="uq_ticket_events_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("service_tickets.id", ondelete="RESTRICT"), index=True,
    )
    ticket_version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))
    from_status: Mapped[str] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    reviewer: Mapped[str] = mapped_column(String(100))
    comment: Mapped[str | None] = mapped_column(Text)
    final_response: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
    )
