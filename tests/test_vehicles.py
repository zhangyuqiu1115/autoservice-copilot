from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
)


@event.listens_for(test_engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection: Any,
    _connection_record: Any,
) -> None:
    """在测试数据库中启用外键约束。"""

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def override_get_db() -> Generator[Session, None, None]:
    """使用测试数据库替代真实数据库。"""

    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """为每个测试创建干净的数据库。"""

    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_vehicle_crud_lifecycle(client: TestClient) -> None:
    """测试创建、查询、更新、重复检查和删除车辆。"""

    vehicle_payload = {
        "vin": "LHGCM82633A004352",
        "brand": "BYD",
        "model": "Han EV",
        "model_year": 2025,
        "powertrain_type": "bev",
    }

    create_response = client.post(
        "/api/v1/vehicles",
        json=vehicle_payload,
    )

    assert create_response.status_code == 201

    created_vehicle = create_response.json()
    vehicle_id = created_vehicle["id"]

    assert created_vehicle["vin"] == vehicle_payload["vin"]
    assert created_vehicle["brand"] == "BYD"
    assert created_vehicle["powertrain_type"] == "bev"

    list_response = client.get("/api/v1/vehicles")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(
        f"/api/v1/vehicles/{vehicle_id}",
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == vehicle_id

    update_response = client.patch(
        f"/api/v1/vehicles/{vehicle_id}",
        json={"model": "Han EV Performance"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["model"] == "Han EV Performance"

    duplicate_response = client.post(
        "/api/v1/vehicles",
        json=vehicle_payload,
    )

    assert duplicate_response.status_code == 409

    delete_response = client.delete(
        f"/api/v1/vehicles/{vehicle_id}",
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""

    missing_response = client.get(
        f"/api/v1/vehicles/{vehicle_id}",
    )

    assert missing_response.status_code == 404


def test_create_vehicle_rejects_invalid_vin(
    client: TestClient,
) -> None:
    """VIN 格式错误时返回 422。"""

    response = client.post(
        "/api/v1/vehicles",
        json={
            "vin": "INVALID",
            "brand": "BYD",
            "model": "Han EV",
            "model_year": 2025,
            "powertrain_type": "bev",
        },
    )

    assert response.status_code == 422