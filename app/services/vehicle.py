from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate


class VehicleAlreadyExistsError(Exception):
    """VIN 已经存在。"""

    def __init__(self, vin: str) -> None:
        self.vin = vin
        super().__init__(f"Vehicle with VIN '{vin}' already exists.")


class VehicleNotFoundError(Exception):
    """指定车辆不存在。"""

    def __init__(self, vehicle_id: int) -> None:
        self.vehicle_id = vehicle_id
        super().__init__(f"Vehicle with ID {vehicle_id} was not found.")


class VehicleDeleteRestrictedError(Exception):
    """车辆存在关联工单，因此不能删除。"""

    def __init__(self, vehicle_id: int) -> None:
        self.vehicle_id = vehicle_id
        super().__init__(
            f"Vehicle with ID {vehicle_id} cannot be deleted "
            "because service tickets reference it."
        )


def get_vehicle_by_id(
    db: Session,
    vehicle_id: int,
) -> Vehicle:
    """根据数据库主键查询车辆。"""

    vehicle = db.get(Vehicle, vehicle_id)

    if vehicle is None:
        raise VehicleNotFoundError(vehicle_id)

    return vehicle


def get_vehicle_by_vin(
    db: Session,
    vin: str,
) -> Vehicle | None:
    """根据 VIN 查询车辆。"""

    statement = select(Vehicle).where(Vehicle.vin == vin)
    return db.scalar(statement)


def list_vehicles(
    db: Session,
    offset: int = 0,
    limit: int = 20,
) -> list[Vehicle]:
    """分页查询车辆，并按 ID 升序排列。"""

    statement = (
        select(Vehicle)
        .order_by(Vehicle.id)
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def create_vehicle(
    db: Session,
    vehicle_data: VehicleCreate,
) -> Vehicle:
    """创建车辆，并阻止重复 VIN。"""

    existing_vehicle = get_vehicle_by_vin(
        db,
        vehicle_data.vin,
    )

    if existing_vehicle is not None:
        raise VehicleAlreadyExistsError(vehicle_data.vin)

    vehicle = Vehicle(**vehicle_data.model_dump())
    db.add(vehicle)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise VehicleAlreadyExistsError(vehicle_data.vin) from error

    db.refresh(vehicle)
    return vehicle


def update_vehicle(
    db: Session,
    vehicle_id: int,
    vehicle_data: VehicleUpdate,
) -> Vehicle:
    """更新一辆已经存在的车辆。"""

    vehicle = get_vehicle_by_id(db, vehicle_id)

    update_data = vehicle_data.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    for attribute_name, value in update_data.items():
        setattr(vehicle, attribute_name, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(vehicle)
    return vehicle


def delete_vehicle(
    db: Session,
    vehicle_id: int,
) -> None:
    """删除没有关联工单的车辆。"""

    vehicle = get_vehicle_by_id(db, vehicle_id)
    db.delete(vehicle)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise VehicleDeleteRestrictedError(vehicle_id) from error