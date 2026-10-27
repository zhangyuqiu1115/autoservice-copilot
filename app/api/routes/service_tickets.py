from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.core.review_security import require_review_key
from app.db.session import get_db
from app.models.enums import TicketStatus
from app.schemas.service_ticket import (
    ServiceTicketResponse,
    TicketActionRequest,
    TicketEventResponse,
    TicketReviewRequest,
)
from app.services import service_ticket

router = APIRouter(prefix="/service-tickets", tags=["service-tickets"])


@router.get("", response_model=list[ServiceTicketResponse])
def list_tickets(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    vehicle_id: Annotated[int | None, Query(gt=0)] = None,
    status: TicketStatus | None = None,
) -> list[ServiceTicketResponse]:
    """分页查看工单，支持按车辆过滤。"""

    return service_ticket.list_tickets(
        db, offset=offset, limit=limit, vehicle_id=vehicle_id, status=status,
    )


@router.get("/{ticket_id}", response_model=ServiceTicketResponse)
def get_ticket(
    ticket_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
) -> ServiceTicketResponse:
    """查看工单当前状态和版本号。"""

    try:
        return service_ticket.get_ticket(db, ticket_id)
    except service_ticket.TicketNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _transition_error(error: Exception) -> HTTPException:
    if isinstance(error, service_ticket.TicketNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, service_ticket.TicketTransitionError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=503, detail=str(error))


@router.post(
    "/{ticket_id}/review",
    response_model=ServiceTicketResponse,
    dependencies=[Depends(require_review_key)],
)
def review_ticket(
    ticket_id: Annotated[int, Path(gt=0)],
    request: TicketReviewRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ServiceTicketResponse:
    """人工批准或退回；批准必须显式提供最终答复。"""

    try:
        return service_ticket.review_ticket(db, ticket_id, request)
    except (
        service_ticket.TicketNotFoundError,
        service_ticket.TicketTransitionError,
        service_ticket.TicketStorageError,
    ) as error:
        raise _transition_error(error) from error


@router.post(
    "/{ticket_id}/submit-for-review",
    response_model=ServiceTicketResponse,
    dependencies=[Depends(require_review_key)],
)
def resubmit_ticket(
    ticket_id: Annotated[int, Path(gt=0)],
    request: TicketActionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ServiceTicketResponse:
    """将被退回的草稿重新提交人工审核。"""

    try:
        return service_ticket.resubmit_ticket(db, ticket_id, request)
    except (
        service_ticket.TicketNotFoundError,
        service_ticket.TicketTransitionError,
        service_ticket.TicketStorageError,
    ) as error:
        raise _transition_error(error) from error


@router.post(
    "/{ticket_id}/close",
    response_model=ServiceTicketResponse,
    dependencies=[Depends(require_review_key)],
)
def close_ticket(
    ticket_id: Annotated[int, Path(gt=0)],
    request: TicketActionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ServiceTicketResponse:
    """关闭已批准工单，保留最终答复和审批时间。"""

    try:
        return service_ticket.close_ticket(db, ticket_id, request)
    except (
        service_ticket.TicketNotFoundError,
        service_ticket.TicketTransitionError,
        service_ticket.TicketStorageError,
    ) as error:
        raise _transition_error(error) from error


@router.get(
    "/{ticket_id}/events",
    response_model=list[TicketEventResponse],
    dependencies=[Depends(require_review_key)],
)
def list_ticket_events(
    ticket_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[TicketEventResponse]:
    """分页读取审核历史。"""

    try:
        return service_ticket.list_ticket_events(db, ticket_id, offset=offset, limit=limit)
    except service_ticket.TicketNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
