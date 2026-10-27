from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import RiskLevel, TicketStatus


class ServiceTicketResponse(BaseModel):
    """工单当前状态；AI 建议与人工最终答复分别存储。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    version: int
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


class TicketActionRequest(BaseModel):
    """审核端提交显示中的版本号，阻止过期页面覆盖较新的决策。"""

    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1, max_length=100)
    expected_version: int = Field(ge=1)
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("reviewer", "comment", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class TicketReviewRequest(TicketActionRequest):
    decision: Literal["approve", "reject"]
    final_response: str | None = Field(default=None, max_length=10000)

    @field_validator("final_response", mode="before")
    @classmethod
    def strip_response(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if self.decision == "approve" and not self.final_response:
            raise ValueError("Approval requires a non-blank final_response.")
        if self.decision == "reject":
            if not self.comment:
                raise ValueError("Rejection requires a non-blank comment.")
            if self.final_response is not None:
                raise ValueError("Rejection must not include a final_response.")
        return self


class TicketEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    ticket_version: int
    action: Literal["approve", "reject", "resubmit", "close"]
    from_status: TicketStatus
    to_status: TicketStatus
    reviewer: str
    comment: str | None
    final_response: str | None
    created_at: datetime
