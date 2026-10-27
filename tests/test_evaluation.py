import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from evaluation import run


@pytest.mark.parametrize(("retrieved", "expected", "rr"), [
    ([7, 8, 9], [8, 9], 0.5), ([7, 8], [7], 1.0),
    ([7, 8], [9], 0.0), ([], [9], 0.0), ([7], [], 0.0),
])
def test_reciprocal_rank_uses_first_relevant_hit(
    retrieved: list[int], expected: list[int], rr: float,
) -> None:
    assert run.reciprocal_rank(retrieved, expected) == rr


def test_metrics_keep_errors_and_misses_in_denominator() -> None:
    questions = [
        {"answerable": True, "document_id": None, "hit": True, "rr": 0.5,
         "citation_count": 2, "valid_citations": 2, "cited_gold": 1, "answer_ms": 12},
        {"answerable": True, "document_id": None, "error": "unavailable"},
        {"answerable": False, "document_id": 2, "refused": True, "filter_ok": True,
         "citation_count": 0, "valid_citations": 0, "cited_gold": 0, "answer_ms": 8},
        {"answerable": False, "document_id": 3, "refused": False, "filter_ok": False,
         "citation_count": 1, "valid_citations": 0, "cited_gold": 0, "answer_ms": 10},
    ]
    risks = [
        {"expected_handoff": True, "predicted_handoff": True, "risk_correct": True},
        {"expected_handoff": True, "predicted_handoff": False, "risk_correct": False},
        {"expected_handoff": False, "predicted_handoff": True, "risk_correct": False},
    ]
    metrics = run.summarize(questions, risks)
    assert metrics["retrieval_hit_at_k"] == 0.5
    assert metrics["retrieval_mrr_at_k"] == 0.25
    assert metrics["answerable_evidence_coverage"] == 0.5
    assert metrics["unanswerable_refusal_rate"] == 0.5
    assert metrics["citation_integrity"] == pytest.approx(2 / 3)
    assert metrics["gold_citation_precision"] == pytest.approx(1 / 3)
    assert metrics["document_filter_accuracy"] == 0.5
    assert metrics["handoff_recall"] == 0.5
    assert metrics["routine_over_handoff_rate"] == 1.0
    assert metrics["risk_accuracy"] == pytest.approx(1 / 3)
    assert metrics["question_errors"] == 1
    assert metrics["median_answer_ms"] == 10
    assert run.check_gates(metrics)["no_question_errors"] is False


def test_empty_metrics_are_not_reported_as_perfect() -> None:
    metrics = run.summarize([], [])
    assert metrics["citation_integrity"] is None
    assert metrics["retrieval_hit_at_k"] is None
    assert metrics["risk_accuracy"] is None
    assert not all(run.check_gates(metrics).values())


@pytest.mark.parametrize("corruption", ["gold", "filter", "duplicate", "version"])
def test_invalid_dataset_is_rejected(tmp_path: Path, corruption: str) -> None:
    for name in ("corpus.json", "questions.json", "safety_cases.json"):
        shutil.copyfile(run.DATASET / name, tmp_path / name)
    question_file = tmp_path / "questions.json"
    data = json.loads(question_file.read_text(encoding="utf-8"))
    if corruption == "gold":
        data["cases"][0]["expected_chunk_ids"] = [999]
    elif corruption == "filter":
        data["cases"][0]["document_id"] = 999
    elif corruption == "duplicate":
        data["cases"].append(data["cases"][0])
    else:
        data["dataset_version"] = "wrong-version"
    question_file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        run.load_dataset(tmp_path)


def test_evaluation_injects_memory_client_and_does_not_call_external_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None, rag_provider="openai_compatible",
        llm_base_url="https://example.invalid/v1", llm_model="never-call",
        review_api_key="private-evaluation-key",
    )
    monkeypatch.setattr(run, "get_settings", lambda: settings)
    monkeypatch.setattr(run.vector_store, "get_embedding_dimension", lambda: 2)
    monkeypatch.setattr(run.vector_store, "embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])
    monkeypatch.setattr(run.vector_store, "embed_query", lambda query: [1.0, 0.0])

    def forbidden_call(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Evaluation must not use persisted Qdrant or external LLM")

    monkeypatch.setattr(run.vector_store, "get_qdrant_client", forbidden_call)
    monkeypatch.setattr(run.rag, "_generate_openai_compatible_answer", forbidden_call)
    report = run.evaluate()
    assert report["configuration"]["provider"] == "extractive"
    assert report["counts"] == {"chunks": 8, "questions": 20, "safety": 20}
    assert report["metrics"]["question_errors"] == 0
    assert "private-evaluation-key" not in json.dumps(report)
    assert all(len(digest) == 64 for digest in report["source_sha256"].values())
    markdown = run.render_markdown(report)
    assert "合成测试集" in markdown
    assert "风险分级或路由不一致案例" in markdown


def test_check_mode_returns_failure_and_still_saves_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = {"metrics": {}, "gates": {"handoff_recall": False}, "acceptance_passed": False}
    monkeypatch.setattr(run, "evaluate", lambda directory: report)
    monkeypatch.setattr(run, "render_markdown", lambda value: "Failed quality gates\n")
    output = tmp_path / "report.json"
    assert run.main(["--check", "--output", str(output)]) == 2
    assert json.loads(output.read_text(encoding="utf-8"))["acceptance_passed"] is False
    assert output.with_suffix(".md").is_file()


def test_normal_mode_completes_without_claiming_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = {"metrics": {}, "gates": {"risk_accuracy": False}, "acceptance_passed": False}
    monkeypatch.setattr(run, "evaluate", lambda directory: report)
    monkeypatch.setattr(run, "render_markdown", lambda value: "Failed quality gates\n")
    output = tmp_path / "report.json"
    assert run.main(["--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["gates"]["risk_accuracy"] is False
