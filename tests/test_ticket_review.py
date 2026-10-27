from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core import review_security
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.enums import RiskLevel, TicketStatus
from app.models.service_ticket import ServiceTicket
from app.models.ticket_event import TicketEvent
from app.models.vehicle import Vehicle
from app.schemas.service_ticket import TicketActionRequest, TicketReviewRequest
from app.services import service_ticket

REVIEW_HEADERS = {"X-Review-Key": "test-review-key"}


@pytest.fixture
def review_engine() -> Generator[Engine, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection: Any, record: Any) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(review_engine: Engine) -> Generator[Session, None, None]:
    with Session(review_engine, expire_on_commit=False) as session:
        session.add(Vehicle(
            vin="LHGCM82633A004352", brand="BYD", model="Han EV",
            model_year=2025, powertrain_type="bev",
        ))
        session.flush()
        session.add(ServiceTicket(
            ticket_number="ASC-REVIEW-TEST", vehicle_id=1,
            customer_question="电池冒烟了", risk_level=RiskLevel.CRITICAL,
            status=TicketStatus.PENDING_REVIEW, requires_human_review=True,
            recommended_action="AI 原始建议，等待人工确认。",
        ))
        session.commit()
        yield session


@pytest.fixture
def client(db: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    def override_db() -> Generator[Session, None, None]:
        yield db

    monkeypatch.setattr(
        review_security, "get_settings",
        lambda: Settings(_env_file=None, review_api_key="test-review-key"),
    )
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def review_payload(**overrides: Any) -> dict[str, Any]:
    return {
        "reviewer": "售后审核员", "expected_version": 1, "decision": "approve",
        "final_response": "已人工核对，请联系授权服务中心处理。", **overrides,
    }


def test_approve_and_close_preserve_human_response_and_audit(
    client: TestClient, db: Session,
) -> None:
    response = client.post(
        "/api/v1/service-tickets/1/review", json=review_payload(), headers=REVIEW_HEADERS,
    )
    assert response.status_code == 200
    approved = response.json()
    assert approved["status"] == "approved"
    assert approved["version"] == 2
    assert approved["requires_human_review"] is False
    assert approved["approved_at"] is not None
    assert approved["closed_at"] is None
    assert approved["final_response"] == review_payload()["final_response"]
    assert approved["recommended_action"] == "AI 原始建议，等待人工确认。"
    closed_response = client.post(
        "/api/v1/service-tickets/1/close",
        json={"reviewer": "售后审核员", "expected_version": 2, "comment": "已处理完毕"},
        headers=REVIEW_HEADERS,
    )
    assert closed_response.status_code == 200
    closed = closed_response.json()
    assert closed["status"] == "closed"
    assert closed["version"] == 3
    assert closed["approved_at"] == approved["approved_at"]
    assert closed["closed_at"] is not None
    assert closed["final_response"] == approved["final_response"]
    history = client.get("/api/v1/service-tickets/1/events", headers=REVIEW_HEADERS)
    assert history.status_code == 200
    events = history.json()
    assert [item["action"] for item in events] == ["approve", "close"]
    assert [item["ticket_version"] for item in events] == [2, 3]
    assert events[0]["from_status"] == "pending_review"
    assert events[1]["to_status"] == "closed"
    assert events[0]["reviewer"] == "售后审核员"
    assert events[1]["comment"] == "已处理完毕"
    assert events[1]["final_response"] == closed["final_response"]
    assert len(client.get("/api/v1/service-tickets?status=closed").json()) == 1
    assert client.get("/api/v1/service-tickets?status=pending_review").json() == []
    assert client.get("/api/v1/service-tickets?status=invalid").status_code == 422
    page = client.get(
        "/api/v1/service-tickets/1/events?offset=1&limit=1", headers=REVIEW_HEADERS,
    ).json()
    assert len(page) == 1 and page[0]["action"] == "close"
    db.expire_all()
    assert db.get(ServiceTicket, 1).status == TicketStatus.CLOSED


def test_reject_resubmit_and_approve_record_complete_history(client: TestClient) -> None:
    rejected = client.post(
        "/api/v1/service-tickets/1/review", headers=REVIEW_HEADERS,
        json=review_payload(decision="reject", final_response=None, comment="补充现场检查依据"),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "draft"
    assert rejected.json()["requires_human_review"] is True
    assert rejected.json()["final_response"] is None
    assert rejected.json()["approved_at"] is None
    resubmitted = client.post(
        "/api/v1/service-tickets/1/submit-for-review", headers=REVIEW_HEADERS,
        json={"reviewer": "处理人员", "expected_version": 2, "comment": "已补充依据，请重新审核"},
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "pending_review"
    assert resubmitted.json()["version"] == 3
    approved = client.post(
        "/api/v1/service-tickets/1/review", headers=REVIEW_HEADERS,
        json=review_payload(expected_version=3),
    )
    assert approved.status_code == 200
    history = client.get("/api/v1/service-tickets/1/events", headers=REVIEW_HEADERS).json()
    assert [item["action"] for item in history] == ["reject", "resubmit", "approve"]
    assert [item["ticket_version"] for item in history] == [2, 3, 4]


@pytest.mark.parametrize("headers", [{}, {"X-Review-Key": "wrong"}])
@pytest.mark.parametrize("path", ["review", "close", "submit-for-review", "events"])
def test_review_operations_require_credentials(
    client: TestClient, db: Session, headers: dict[str, str], path: str,
) -> None:
    endpoint = f"/api/v1/service-tickets/1/{path}"
    response = (
        client.get(endpoint, headers=headers) if path == "events"
        else client.post(endpoint, json=review_payload(), headers=headers)
    )
    assert response.status_code == 403
    assert db.scalar(select(func.count()).select_from(TicketEvent)) == 0
    assert db.get(ServiceTicket, 1).status == TicketStatus.PENDING_REVIEW


def test_unconfigured_review_is_disabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_security, "get_settings", lambda: Settings(_env_file=None))
    response = client.post(
        "/api/v1/service-tickets/1/review", json=review_payload(), headers=REVIEW_HEADERS,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Human review is not configured."


@pytest.mark.parametrize("overrides", [
    {"final_response": None}, {"final_response": "   "}, {"reviewer": "   "},
    {"expected_version": 0}, {"decision": "invalid"}, {"status": "closed"},
    {"decision": "reject", "final_response": None, "comment": "   "},
    {"decision": "reject", "comment": "需要修改", "final_response": "不允许带入最终答复"},
])
def test_invalid_review_payloads_do_not_change_state(
    client: TestClient, db: Session, overrides: dict[str, Any],
) -> None:
    response = client.post(
        "/api/v1/service-tickets/1/review", json=review_payload(**overrides),
        headers=REVIEW_HEADERS,
    )
    assert response.status_code == 422
    assert db.get(ServiceTicket, 1).version == 1
    assert db.scalar(select(func.count()).select_from(TicketEvent)) == 0


@pytest.mark.parametrize("path", ["close", "submit-for-review"])
def test_invalid_transitions_are_conflicts(client: TestClient, path: str) -> None:
    response = client.post(
        f"/api/v1/service-tickets/1/{path}", headers=REVIEW_HEADERS,
        json={"reviewer": "审核人员", "expected_version": 1},
    )
    assert response.status_code == 409


def test_stale_version_and_duplicate_decisions_are_rejected(client: TestClient) -> None:
    assert client.post(
        "/api/v1/service-tickets/1/review", json=review_payload(), headers=REVIEW_HEADERS,
    ).status_code == 200
    assert client.post(
        "/api/v1/service-tickets/1/review", json=review_payload(), headers=REVIEW_HEADERS,
    ).status_code == 409
    assert client.post(
        "/api/v1/service-tickets/1/close", headers=REVIEW_HEADERS,
        json={"reviewer": "审核员", "expected_version": 1},
    ).status_code == 409
    assert len(client.get(
        "/api/v1/service-tickets/1/events", headers=REVIEW_HEADERS,
    ).json()) == 1


def test_old_version_remains_invalid_after_rejection_cycle(client: TestClient) -> None:
    assert client.post(
        "/api/v1/service-tickets/1/review", headers=REVIEW_HEADERS,
        json=review_payload(decision="reject", final_response=None, comment="重新确认"),
    ).status_code == 200
    assert client.post(
        "/api/v1/service-tickets/1/submit-for-review", headers=REVIEW_HEADERS,
        json={"reviewer": "审核员", "expected_version": 2},
    ).status_code == 200
    assert client.post(
        "/api/v1/service-tickets/1/review", json=review_payload(), headers=REVIEW_HEADERS,
    ).status_code == 409


def test_stale_session_cannot_overwrite_another_reviewer(
    db: Session, review_engine: Engine,
) -> None:
    cached = db.get(ServiceTicket, 1)
    assert cached.version == 1
    with Session(review_engine) as other:
        service_ticket.review_ticket(other, 1, TicketReviewRequest(**review_payload()))
    # The first session still holds version 1, so the SQL conditional update must reject it.
    assert cached.version == 1
    with pytest.raises(service_ticket.TicketTransitionError):
        service_ticket.review_ticket(db, 1, TicketReviewRequest(**review_payload()))
    db.expire_all()
    assert db.get(ServiceTicket, 1).version == 2
    assert db.scalar(select(func.count()).select_from(TicketEvent)) == 1


def test_audit_insert_failure_rolls_back_ticket_update(client: TestClient, db: Session) -> None:
    def fail_audit_insert(*args: Any) -> None:
        raise SQLAlchemyError("simulated audit storage failure")

    event.listen(TicketEvent, "before_insert", fail_audit_insert)
    try:
        response = client.post(
            "/api/v1/service-tickets/1/review", json=review_payload(), headers=REVIEW_HEADERS,
        )
    finally:
        event.remove(TicketEvent, "before_insert", fail_audit_insert)
    assert response.status_code == 503
    db.expire_all()
    ticket = db.get(ServiceTicket, 1)
    assert ticket.status == TicketStatus.PENDING_REVIEW
    assert ticket.version == 1
    assert ticket.final_response is None
    assert db.scalar(select(func.count()).select_from(TicketEvent)) == 0


def test_closed_tickets_cannot_be_reviewed_or_closed_again(client: TestClient) -> None:
    client.post("/api/v1/service-tickets/1/review", json=review_payload(), headers=REVIEW_HEADERS)
    client.post(
        "/api/v1/service-tickets/1/close", headers=REVIEW_HEADERS,
        json={"reviewer": "审核员", "expected_version": 2},
    )
    assert client.post(
        "/api/v1/service-tickets/1/review", headers=REVIEW_HEADERS,
        json=review_payload(expected_version=3),
    ).status_code == 409
    assert client.post(
        "/api/v1/service-tickets/1/close", headers=REVIEW_HEADERS,
        json={"reviewer": "审核员", "expected_version": 3},
    ).status_code == 409


@pytest.mark.parametrize("path", ["review", "close", "submit-for-review", "events"])
def test_missing_ticket_returns_404(client: TestClient, path: str) -> None:
    endpoint = f"/api/v1/service-tickets/999/{path}"
    if path == "events":
        response = client.get(endpoint, headers=REVIEW_HEADERS)
    else:
        payload = review_payload() if path == "review" else {
            "reviewer": "审核员", "expected_version": 1,
        }
        response = client.post(endpoint, json=payload, headers=REVIEW_HEADERS)
    assert response.status_code == 404


def test_review_secret_is_masked() -> None:
    settings = Settings(_env_file=None, review_api_key="private-review-key")
    assert "private-review-key" not in repr(settings)


def test_review_and_close_do_not_call_rag(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import rag

    def unexpected_rag(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Human review must not generate an automatic final response")

    monkeypatch.setattr(rag, "answer_question", unexpected_rag)
    service_ticket.review_ticket(db, 1, TicketReviewRequest(**review_payload()))
    closed = service_ticket.close_ticket(
        db, 1, TicketActionRequest(reviewer="审核员", expected_version=2),
    )
    assert closed.final_response == review_payload()["final_response"]


def test_agent_created_ticket_supports_full_human_review_lifecycle(client: TestClient) -> None:
    created = client.post(
        "/api/v1/agent/triage", json={"vehicle_id": 1, "query": "电池冒烟了"},
    )
    assert created.status_code == 201
    ticket = created.json()
    assert ticket["version"] == 1
    assert ticket["risk_level"] == "critical"
    endpoint = f"/api/v1/service-tickets/{ticket['id']}"
    approved = client.post(
        endpoint + "/review", headers=REVIEW_HEADERS,
        json=review_payload(expected_version=ticket["version"]),
    )
    assert approved.status_code == 200
    closed = client.post(
        endpoint + "/close", headers=REVIEW_HEADERS,
        json={"reviewer": "审核员", "expected_version": approved.json()["version"]},
    )
    assert closed.status_code == 200
    detail = client.get(endpoint).json()
    assert detail["status"] == "closed"
    assert detail["version"] == 3
    assert detail["risk_level"] == "critical"
    assert detail["final_response"] == review_payload()["final_response"]
    history = client.get(endpoint + "/events", headers=REVIEW_HEADERS).json()
    assert [item["action"] for item in history] == ["approve", "close"]
