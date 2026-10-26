from pydantic import Field

from app.schemas.rag import RagAnswerRequest, RagCitationResponse
from app.schemas.service_ticket import ServiceTicketResponse


class AgentTriageRequest(RagAnswerRequest):
    """一次分流请求会为指定车辆创建一个待审核工单。"""

    vehicle_id: int = Field(ge=1)


class AgentTriageResponse(ServiceTicketResponse):
    """工单及本次执行的证据、风险和节点路径。"""

    grounded: bool
    citations: list[RagCitationResponse]
    execution_path: list[str]
