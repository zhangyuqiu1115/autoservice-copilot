from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.enums import TicketStatus
from app.models.service_ticket import ServiceTicket
from app.models.ticket_event import TicketEvent
from app.schemas.agent import AgentTriageRequest, AgentTriageResponse
from app.schemas.service_ticket import (
    ServiceTicketResponse,
    TicketActionRequest,
    TicketReviewRequest,
)
from app.services import agent, document, vehicle


class TicketNotFoundError(Exception):
    """指定工单不存在。"""


class TicketStorageError(Exception):
    """工单事务保存失败。"""


class TicketTransitionError(Exception):
    """状态或版本不符，需要重新读取工单再操作。"""


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
    status: TicketStatus | None = None,
) -> list[ServiceTicket]:
    statement = select(ServiceTicket).order_by(ServiceTicket.id.desc())
    if vehicle_id is not None:
        statement = statement.where(ServiceTicket.vehicle_id == vehicle_id)
    if status is not None:
        statement = statement.where(ServiceTicket.status == status)
    return list(db.scalars(statement.offset(offset).limit(limit)).all())


def get_ticket(db: Session, ticket_id: int) -> ServiceTicket:
    ticket = db.get(ServiceTicket, ticket_id)
    if ticket is None:
        raise TicketNotFoundError(f"Service ticket with ID {ticket_id} was not found.")
    return ticket


def _transition_ticket(
    db: Session,
    ticket_id: int,
    request: TicketActionRequest,
    action: Literal["approve", "reject", "resubmit", "close"],
    *,
    final_response: str | None = None,
) -> ServiceTicket:
    """条件更新工单和追加审核事件位于同一事务。"""

    transitions = {
        "approve": (TicketStatus.PENDING_REVIEW, TicketStatus.APPROVED),
        "reject": (TicketStatus.PENDING_REVIEW, TicketStatus.DRAFT),
        "resubmit": (TicketStatus.DRAFT, TicketStatus.PENDING_REVIEW),
        "close": (TicketStatus.APPROVED, TicketStatus.CLOSED),
    }
    from_status, to_status = transitions[action]
    ticket = get_ticket(db, ticket_id)
    if ticket.status != from_status or ticket.version != request.expected_version:
        raise TicketTransitionError(
            "Ticket status or version has changed; refresh the ticket before retrying."
        )

    now = datetime.now(UTC)
    values: dict[str, object] = {
        "status": to_status,
        "version": request.expected_version + 1,
        "updated_at": now,
    }
    if action == "approve":
        values.update(
            final_response=final_response,
            approved_at=now,
            requires_human_review=False,
        )
    elif action in {"reject", "resubmit"}:
        values.update(
            final_response=None,
            approved_at=None,
            closed_at=None,
            requires_human_review=True,
        )
    elif action == "close":
        values.update(closed_at=now)

    response_snapshot = ticket.final_response if action == "close" else final_response
    try:
        result = db.execute(
            update(ServiceTicket)
            .where(
                ServiceTicket.id == ticket_id,
                ServiceTicket.status == from_status,
                ServiceTicket.version == request.expected_version,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            db.rollback()
            raise TicketTransitionError("Another reviewer updated this ticket; refresh and retry.")

        db.add(
            TicketEvent(
                ticket_id=ticket_id,
                ticket_version=request.expected_version + 1,
                action=action,
                from_status=from_status.value,
                to_status=to_status.value,
                reviewer=request.reviewer,
                comment=request.comment,
                final_response=response_snapshot,
                created_at=now,
            )
        )
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise TicketStorageError("Could not save the review operation.") from error

    db.refresh(ticket)
    return ticket


def review_ticket(db: Session, ticket_id: int, request: TicketReviewRequest) -> ServiceTicket:
    return _transition_ticket(
        db, ticket_id, request, request.decision, final_response=request.final_response,
    )


def resubmit_ticket(db: Session, ticket_id: int, request: TicketActionRequest) -> ServiceTicket:
    return _transition_ticket(db, ticket_id, request, "resubmit")


def close_ticket(db: Session, ticket_id: int, request: TicketActionRequest) -> ServiceTicket:
    return _transition_ticket(db, ticket_id, request, "close")


def list_ticket_events(
    db: Session, ticket_id: int, *, offset: int = 0, limit: int = 20,
) -> list[TicketEvent]:
    get_ticket(db, ticket_id)
    statement = (
        select(TicketEvent)
        .where(TicketEvent.ticket_id == ticket_id)
        .order_by(TicketEvent.id)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement).all())
