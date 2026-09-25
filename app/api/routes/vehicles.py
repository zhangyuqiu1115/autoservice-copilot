from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.vehicle import (
    VehicleCreate,
    VehicleResponse,
    VehicleUpdate,
)
from app.services import vehicle as vehicle_service

router = APIRouter(
    prefix="/vehicles",
    tags=["vehicles"],
)


@router.post(
    "",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_vehicle(
    vehicle_data: VehicleCreate,
    db: Annotated[Session, Depends(get_db)],
) -> VehicleResponse:
    """创建车辆。"""

    try:
        return vehicle_service.create_vehicle(db, vehicle_data)
    except vehicle_service.VehicleAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[VehicleResponse],
)
def list_vehicles(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[VehicleResponse]:
    """分页查询车辆。"""

    return vehicle_service.list_vehicles(
        db,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{vehicle_id}",
    response_model=VehicleResponse,
)
def get_vehicle(
    vehicle_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
) -> VehicleResponse:
    """根据 ID 查询车辆。"""

    try:
        return vehicle_service.get_vehicle_by_id(
            db,
            vehicle_id,
        )
    except vehicle_service.VehicleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.patch(
    "/{vehicle_id}",
    response_model=VehicleResponse,
)
def update_vehicle(
    vehicle_id: Annotated[int, Path(gt=0)],
    vehicle_data: VehicleUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> VehicleResponse:
    """更新车辆。"""

    try:
        return vehicle_service.update_vehicle(
            db,
            vehicle_id,
            vehicle_data,
        )
    except vehicle_service.VehicleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.delete(
    "/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_vehicle(
    vehicle_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """删除没有关联工单的车辆。"""

    try:
        vehicle_service.delete_vehicle(
            db,
            vehicle_id,
        )
    except vehicle_service.VehicleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except vehicle_service.VehicleDeleteRestrictedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)