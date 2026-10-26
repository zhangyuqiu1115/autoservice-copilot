from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.agent import AgentTriageRequest, AgentTriageResponse
from app.services import document, service_ticket, vehicle

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/triage", response_model=AgentTriageResponse, status_code=status.HTTP_201_CREATED)
def triage_request(
    request: AgentTriageRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AgentTriageResponse:
    """分流售后问题并创建待审核工单；每次请求创建一个新工单。"""

    try:
        return service_ticket.create_triaged_ticket(db, request)
    except (vehicle.VehicleNotFoundError, document.DocumentNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except service_ticket.TicketStorageError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
