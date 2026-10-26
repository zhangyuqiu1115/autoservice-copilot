from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.enums import TicketStatus
from app.models.service_ticket import ServiceTicket
from app.schemas.agent import AgentTriageRequest, AgentTriageResponse
from app.schemas.service_ticket import ServiceTicketResponse
from app.services import agent, document, vehicle


class TicketNotFoundError(Exception):
    """指定工单不存在。"""


class TicketStorageError(Exception):
    """工单事务保存失败。"""


def create_triaged_ticket(db: Session, request: AgentTriageRequest) -> AgentTriageResponse:
    """先验证关联实体，执行只读图，最后原子保存待审核工单。"""

    vehicle.get_vehicle_by_id(db, request.vehicle_id)
    if request.document_id is not None:
        document.get_document_by_id(db, request.document_id)

    result = agent.triage_question(
        request.query,
        limit=request.limit,
        document_id=request.document_id,
    )
    sources = ", ".join(
        f"document={item.document_id}/chunk={item.chunk_id}"
        for item in result["citations"]
    )
    ticket = ServiceTicket(
        ticket_number=f"ASC-{uuid4().hex[:28]}",
        vehicle_id=request.vehicle_id,
        customer_question=request.query,
        issue_category=result["issue_category"],
        risk_level=result["risk_level"],
        risk_reason=result["risk_reason"],
        status=TicketStatus.PENDING_REVIEW,
        ai_summary=(
            f"risk={result['risk_level'].value}; grounded={result['grounded']}; "
            f"path={' -> '.join(result['execution_path'])}; sources={sources or 'none'}"
        ),
        recommended_action=result["recommended_action"],
        requires_human_review=True,
    )
    db.add(ticket)
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise TicketStorageError("Could not save the service ticket.") from error

    db.refresh(ticket)
    return AgentTriageResponse(
        **ServiceTicketResponse.model_validate(ticket).model_dump(),
        grounded=result["grounded"],
        citations=result["citations"],
        execution_path=result["execution_path"] + ["save_pending_ticket"],
    )


def list_tickets(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 20,
    vehicle_id: int | None = None,
) -> list[ServiceTicket]:
    statement = select(ServiceTicket).order_by(ServiceTicket.id.desc())
    if vehicle_id is not None:
        statement = statement.where(ServiceTicket.vehicle_id == vehicle_id)
    return list(db.scalars(statement.offset(offset).limit(limit)).all())


def get_ticket(db: Session, ticket_id: int) -> ServiceTicket:
    ticket = db.get(ServiceTicket, ticket_id)
    if ticket is None:
        raise TicketNotFoundError(f"Service ticket with ID {ticket_id} was not found.")
    return ticket
