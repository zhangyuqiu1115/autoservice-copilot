from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import RiskLevel, TicketStatus


class ServiceTicketResponse(BaseModel):
    """工单当前状态；AI 建议与人工最终答复分别存储。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    vehicle_id: int
    customer_question: str
    issue_category: str | None
    risk_level: RiskLevel
    risk_reason: str | None
    status: TicketStatus
    ai_summary: str | None
    recommended_action: str | None
    requires_human_review: bool
    final_response: str | None
    approved_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
