from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.service_ticket import ServiceTicketResponse
from app.services import service_ticket

router = APIRouter(prefix="/service-tickets", tags=["service-tickets"])


@router.get("", response_model=list[ServiceTicketResponse])
def list_tickets(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    vehicle_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[ServiceTicketResponse]:
    """分页查看工单，支持按车辆过滤。"""

    return service_ticket.list_tickets(db, offset=offset, limit=limit, vehicle_id=vehicle_id)


@router.get("/{ticket_id}", response_model=ServiceTicketResponse)
def get_ticket(
    ticket_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
) -> ServiceTicketResponse:
    """查看工单；人工审批将在后续阶段提供。"""

    try:
        return service_ticket.get_ticket(db, ticket_id)
    except service_ticket.TicketNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
