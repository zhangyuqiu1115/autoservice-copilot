"""仅对 loopback 且 ENVIRONMENT=demo 的 API 执行真实 HTTP 演示验收。"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from app.core.config import Settings
from scripts.local import DEFAULT_DATA


def validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Smoke writes are restricted to an HTTP loopback demo API.")
    return value.rstrip("/")


def run_smoke(client: httpx.Client, review_key: str) -> dict[str, object]:
    if not review_key.strip():
        raise ValueError("A private review key is required.")
    started = perf_counter()
    health = client.get("/api/v1/health")
    health.raise_for_status()
    if health.json().get("environment") != "demo":
        raise ValueError("Refusing writes: target API must have ENVIRONMENT=demo.")

    checks = ["health_demo_environment"]

    def require(condition: bool, description: str) -> None:
        if not condition:
            raise RuntimeError(f"Demo acceptance failed: {description}")

    def request(method: str, path: str, expected: int = 200, **kwargs: object):
        response = client.request(method, "/api/v1" + path, **kwargs)
        if response.status_code != expected:
            raise RuntimeError(f"{method} {path}: expected {expected}, got {response.status_code}")
        return response.json()

    run_id = uuid4().hex
    vehicle = request("POST", "/vehicles", 201, json={
        "vin": "DEMV" + run_id[:13].upper(), "brand": "Synthetic Demo",
        "model": "Acceptance EV", "model_year": 2025, "powertrain_type": "bev",
    })
    checks.append("vehicle_created")
    content = (
        f"Synthetic acceptance run: {run_id}\n\n"
        "充电准备：充电前安全驻车，检查充电连接器外观，并确认充电口清洁干燥。\n\n"
        "本资料为合成软件演示材料，不是官方车辆手册；没有规定保修年限。"
    ).encode()
    document = request(
        "POST", "/documents", 201,
        files={"file": ("synthetic-acceptance.txt", content, "text/plain")},
        data={"title": "Synthetic Acceptance " + run_id, "document_type": "owner_manual"},
    )
    document_id = document["id"]
    processed = request("POST", f"/documents/{document_id}/process")
    require(
        processed["processing_status"] == "completed" and processed["chunk_count"] > 0,
        "document processing",
    )
    checks.append("upload_parse_chunk_index")
    question = {"query": "充电之前需要检查什么？", "document_id": document_id, "limit": 3}
    retrieved = request("POST", "/retrieval/search", json=question)
    require(bool(retrieved) and all(item["document_id"] == document_id for item in retrieved),
            "retrieval document filter")
    checks.append("retrieval_filtered")
    answer = request("POST", "/rag/answer", json=question)
    require(bool(answer["grounded"] and answer["citations"]), "grounded RAG answer")
    require(all(item["document_id"] == document_id for item in answer["citations"]),
            "RAG citation document filter")
    checks.append("rag_with_citations")
    refusal = request(
        "POST", "/rag/answer", json={"query": "保修具体几年？", "document_id": document_id},
    )
    require(refusal["mode"] == "no_evidence" and not refusal["citations"], "refusal")
    checks.append("unsupported_fact_refused")

    ticket = request("POST", "/agent/triage", 201, json=question | {"vehicle_id": vehicle["id"]})
    require(ticket["status"] == "pending_review" and ticket["version"] == 1, "new ticket state")
    require(ticket["grounded"] and "evidence_found" in ticket["execution_path"], "agent evidence")
    checks.append("agent_grounded_ticket")
    critical = request(
        "POST", "/agent/triage", 201,
        json={"query": "合成演示：电池冒烟了", "vehicle_id": vehicle["id"]},
    )
    require(critical["risk_level"] == "critical" and critical["status"] == "pending_review",
            "critical ticket state")
    require("human_handoff" in critical["execution_path"] and not critical["citations"],
            "critical human handoff")
    checks.append("critical_human_handoff")

    endpoint = f"/service-tickets/{ticket['id']}"
    payload = {
        "reviewer": "automated-synthetic-smoke", "expected_version": 1, "decision": "approve",
        "final_response": "仅用于合成软件验收，非真实客户审核答复。",
    }
    request("POST", endpoint + "/review", 403, json=payload)
    checks.append("review_auth_required")
    headers = {"X-Review-Key": review_key}
    approved = request("POST", endpoint + "/review", json=payload, headers=headers)
    require(approved["status"] == "approved" and approved["version"] == 2, "approval")
    checks.append("explicit_synthetic_approval")
    request("POST", endpoint + "/review", 409, json=payload, headers=headers)
    checks.append("stale_version_rejected")
    closed = request(
        "POST", endpoint + "/close", headers=headers,
        json={"reviewer": "automated-synthetic-smoke", "expected_version": 2},
    )
    require(closed["status"] == "closed" and closed["final_response"] == payload["final_response"],
            "closed ticket final response")
    history = request("GET", endpoint + "/events", headers=headers)
    require([item["action"] for item in history] == ["approve", "close"], "audit history")
    checks += ["ticket_closed", "audit_history"]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "transport": "real HTTP loopback", "data": "synthetic demo only",
        "run_id": run_id, "passed": True, "checks": checks,
        "duration_seconds": round(perf_counter() - started, 3),
        "vehicle_id": vehicle["id"], "document_id": document_id,
        "closed_ticket_id": ticket["id"], "pending_critical_ticket_id": critical["id"],
    }


def verify_persisted_demo(
    client: httpx.Client, review_key: str, original: dict[str, object],
) -> dict[str, object]:
    health = client.get("/api/v1/health")
    health.raise_for_status()
    if health.json().get("environment") != "demo" or original.get("passed") is not True:
        raise ValueError("Require ENVIRONMENT=demo and a prior successful report.")
    checks = []
    headers = {"X-Review-Key": review_key}

    def checked_get(path: str):
        response = client.get("/api/v1" + path, headers=headers)
        response.raise_for_status()
        return response.json()

    vehicle_id = int(original["vehicle_id"])
    document_id = int(original["document_id"])
    ticket_id = int(original["closed_ticket_id"])
    critical_id = int(original["pending_critical_ticket_id"])
    checked_get(f"/vehicles/{vehicle_id}")
    checks.append("vehicle_persisted")
    document = checked_get(f"/documents/{document_id}")
    if document["processing_status"] != "completed":
        raise RuntimeError("Processed document did not persist.")
    checks.append("document_persisted")
    ticket = checked_get(f"/service-tickets/{ticket_id}")
    history = checked_get(f"/service-tickets/{ticket_id}/events")
    if ticket["status"] != "closed" or [row["action"] for row in history] != ["approve", "close"]:
        raise RuntimeError("Closed ticket and audit history did not persist.")
    checks += ["closed_ticket_persisted", "audit_history_persisted"]
    if checked_get(f"/service-tickets/{critical_id}")["status"] != "pending_review":
        raise RuntimeError("Critical ticket state changed unexpectedly.")
    checks.append("critical_ticket_persisted")
    retrieval = client.post("/api/v1/retrieval/search", json={
        "query": "充电之前需要检查什么？", "document_id": document_id,
    })
    retrieval.raise_for_status()
    if not retrieval.json() or any(row["document_id"] != document_id for row in retrieval.json()):
        raise RuntimeError("Vector index did not persist.")
    checks.append("vector_index_persisted")
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "transport": "real HTTP loopback", "data": "synthetic demo only",
        "passed": True, "checks": checks, "original_run_id": original["run_id"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--key-file", type=Path, default=DEFAULT_DATA / ".review-key")
    parser.add_argument(
        "--verify-report", type=Path, help="重启后只读核验此前 smoke 报告中的数据。",
    )
    parser.add_argument("--output", type=Path, default=Path("reports/demo-acceptance-local.json"))
    args = parser.parse_args(argv)
    base_url = validate_base_url(args.base_url)
    key = Settings().review_api_key
    review_key = key.get_secret_value() if key is not None else ""
    if not review_key.strip():
        review_key = args.key_file.read_text(encoding="utf-8").strip()
    with httpx.Client(base_url=base_url, timeout=120.0, trust_env=False) as client:
        if args.verify_report is not None:
            original = json.loads(args.verify_report.read_text(encoding="utf-8"))
            report = verify_persisted_demo(client, review_key, original)
        else:
            report = run_smoke(client, review_key)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
