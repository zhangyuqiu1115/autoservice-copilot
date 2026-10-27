"""python -m evaluation.run：真实 Embedding + 内存 Qdrant 的固定集评估。"""

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from qdrant_client import QdrantClient

from app.core.config import Settings, get_settings
from app.models.document_chunk import DocumentChunk
from app.models.enums import RiskLevel
from app.services import rag, safety, vector_store

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation"
GATES = {
    "retrieval_hit_at_k": 0.8,
    "citation_integrity": 1.0,
    "unanswerable_refusal_rate": 0.8,
    "handoff_recall": 1.0,
    "risk_accuracy": 0.9,
}


class CorpusChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    chunk_id: int = Field(gt=0)
    document_id: int = Field(gt=0)
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1)


class QuestionCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    answerable: bool
    expected_chunk_ids: list[int]
    document_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_gold(self) -> "QuestionCase":
        if self.answerable != bool(self.expected_chunk_ids):
            raise ValueError("Answerable cases require gold chunks; unanswerable cases need none.")
        return self


class SafetyCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    expected_risk: RiskLevel
    expected_handoff: bool

    @model_validator(mode="after")
    def validate_handoff(self) -> "SafetyCase":
        if self.expected_handoff != (self.expected_risk != RiskLevel.LOW):
            raise ValueError("Only low-risk labels may use the routine route.")
        return self


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_dataset(directory: Path = DATASET) -> dict[str, Any]:
    corpus = _read_json(directory / "corpus.json")
    questions = _read_json(directory / "questions.json")
    risks = _read_json(directory / "safety_cases.json")
    versions = {item["dataset_version"] for item in (corpus, questions, risks)}
    if len(versions) != 1:
        raise ValueError("Dataset versions must match.")
    chunks = [CorpusChunk.model_validate(item) for item in corpus["chunks"]]
    cases = [QuestionCase.model_validate(item) for item in questions["cases"]]
    safety_cases = [SafetyCase.model_validate(item) for item in risks["cases"]]
    for records, key in ((chunks, "chunk_id"), (cases, "id"), (safety_cases, "id")):
        ids = [getattr(item, key) for item in records]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("Dataset IDs must be non-empty and unique.")
    positions = [(item.document_id, item.chunk_index) for item in chunks]
    if len(set(positions)) != len(positions):
        raise ValueError("Document chunk positions must be unique.")
    by_id = {item.chunk_id: item for item in chunks}
    for case in cases:
        for expected_id in case.expected_chunk_ids:
            if expected_id not in by_id:
                raise ValueError(f"Unknown gold chunk in {case.id}.")
            if case.document_id is not None and by_id[expected_id].document_id != case.document_id:
                raise ValueError(f"Gold chunk violates document filter in {case.id}.")
    if not any(case.answerable for case in cases) or not any(not c.answerable for c in cases):
        raise ValueError("Include both answerable and unanswerable cases.")
    if not 1 <= questions["top_k"] <= 20 or not -1 <= questions["min_score"] <= 1:
        raise ValueError("Invalid retrieval configuration.")
    return {
        "version": versions.pop(), "chunks": chunks, "questions": cases,
        "safety": safety_cases, "top_k": questions["top_k"], "min_score": questions["min_score"],
    }


def reciprocal_rank(retrieved_ids: list[int], expected_ids: list[int]) -> float:
    expected = set(expected_ids)
    return next((1.0 / rank for rank, item in enumerate(retrieved_ids, 1) if item in expected), 0.0)


def _ratio(numerator: int | float, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(
    question_rows: list[dict[str, Any]], risk_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    answerable = [row for row in question_rows if row["answerable"]]
    unanswerable = [row for row in question_rows if not row["answerable"]]
    expected_handoffs = [row for row in risk_rows if row["expected_handoff"]]
    expected_routine = [row for row in risk_rows if not row["expected_handoff"]]
    timings = [row["answer_ms"] for row in question_rows if row.get("answer_ms") is not None]
    return {
        "retrieval_hit_at_k": _ratio(
            sum(row.get("hit", False) for row in answerable), len(answerable),
        ),
        "retrieval_mrr_at_k": _ratio(sum(row.get("rr", 0) for row in answerable), len(answerable)),
        "answerable_evidence_coverage": _ratio(
            sum(row.get("cited_gold", 0) > 0 for row in answerable), len(answerable),
        ),
        "citation_integrity": _ratio(
            sum(row.get("valid_citations", 0) for row in question_rows),
            sum(row.get("citation_count", 0) for row in question_rows),
        ),
        "gold_citation_precision": _ratio(
            sum(row.get("cited_gold", 0) for row in question_rows),
            sum(row.get("citation_count", 0) for row in question_rows),
        ),
        "unanswerable_refusal_rate": _ratio(
            sum(row.get("refused", False) for row in unanswerable), len(unanswerable),
        ),
        "document_filter_accuracy": _ratio(
            sum(
                row.get("filter_ok", False)
                for row in question_rows if row["document_id"] is not None
            ),
            sum(row["document_id"] is not None for row in question_rows),
        ),
        "risk_accuracy": _ratio(sum(row["risk_correct"] for row in risk_rows), len(risk_rows)),
        "handoff_recall": _ratio(
            sum(row["predicted_handoff"] for row in expected_handoffs), len(expected_handoffs),
        ),
        "routine_over_handoff_rate": _ratio(
            sum(row["predicted_handoff"] for row in expected_routine), len(expected_routine),
        ),
        "median_answer_ms": statistics.median(timings) if timings else None,
        "question_errors": sum("error" in row for row in question_rows),
    }


def check_gates(metrics: dict[str, Any]) -> dict[str, bool]:
    return {
        name: metrics.get(name) is not None and metrics[name] >= threshold
        for name, threshold in GATES.items()
    } | {"no_question_errors": metrics["question_errors"] == 0}


def _evaluate_question(
    case: QuestionCase, client: QdrantClient, settings: Settings, chunks: dict[int, CorpusChunk],
) -> dict[str, Any]:
    row = case.model_dump()
    try:
        retrieved = vector_store.search_document_chunks(
            case.query, limit=settings.retrieval_top_k, document_id=case.document_id, client=client,
        )
        start = perf_counter()
        answer = rag.answer_question(
            case.query, limit=settings.retrieval_top_k, document_id=case.document_id,
            client=client, settings=settings,
        )
        answer_ms = (perf_counter() - start) * 1000
        citation_ids = [item.chunk_id for item in answer.citations]
        valid_citations = sum(
            citation.chunk_id in chunks
            and chunks[citation.chunk_id].document_id == citation.document_id
            and chunks[citation.chunk_id].chunk_index == citation.chunk_index
            and bool(citation.excerpt.strip())
            and citation.excerpt in chunks[citation.chunk_id].content
            for citation in answer.citations
        )
        rr = reciprocal_rank([item.chunk_id for item in retrieved], case.expected_chunk_ids)
        row.update(
            retrieved=[asdict(item) for item in retrieved],
            answer=asdict(answer), answer_ms=round(answer_ms, 3), hit=rr > 0, rr=rr,
            citation_count=len(citation_ids), valid_citations=valid_citations,
            cited_gold=len(set(citation_ids) & set(case.expected_chunk_ids)),
            refused=answer.mode == "no_evidence" and not answer.grounded and not answer.citations,
            filter_ok=case.document_id is None or (
                all(item.document_id == case.document_id for item in retrieved)
                and all(item.document_id == case.document_id for item in answer.citations)
            ),
        )
    except (rag.RagServiceError, vector_store.VectorStoreError) as error:
        row["error"] = str(error)
    return row


def evaluate(dataset_directory: Path = DATASET) -> dict[str, Any]:
    dataset = load_dataset(dataset_directory)
    base_settings = get_settings()
    settings = base_settings.model_copy(update={
        "rag_provider": "extractive", "rag_min_score": dataset["min_score"],
        "retrieval_top_k": dataset["top_k"], "rag_max_context_chars": 6000,
    })
    by_id = {item.chunk_id: item for item in dataset["chunks"]}
    # Explicit client injection keeps both vector search and RAG away from persisted business data.
    with closing(QdrantClient(location=":memory:")) as client:
        for document_id in sorted({item.document_id for item in by_id.values()}):
            document_chunks = [
                DocumentChunk(
                    id=item.chunk_id, document_id=item.document_id,
                    chunk_index=item.chunk_index, content=item.content,
                    character_count=len(item.content),
                )
                for item in by_id.values() if item.document_id == document_id
            ]
            vector_store.index_document_chunks(document_id, document_chunks, client=client)
        question_rows = [
            _evaluate_question(case, client, settings, by_id) for case in dataset["questions"]
        ]

    risk_rows = []
    for case in dataset["safety"]:
        predicted = safety.assess_risk(case.query)
        risk_rows.append(case.model_dump(mode="json") | {
            "predicted_risk": predicted.risk_level.value,
            "predicted_handoff": predicted.risk_level != RiskLevel.LOW,
            "risk_correct": predicted.risk_level == case.expected_risk,
        })
    metrics = summarize(question_rows, risk_rows)
    gates = check_gates(metrics)
    source_paths = [
        dataset_directory / name for name in ("corpus.json", "questions.json", "safety_cases.json")
    ] + [
        ROOT / name for name in (
            "app/services/rag.py", "app/services/vector_store.py", "app/services/safety.py",
            "app/services/embedding.py", "evaluation/run.py",
        )
    ]
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "dataset_version": dataset["version"], "source_revision_before_report": revision,
        "source_sha256": hashes,
        "configuration": {
            "provider": "extractive", "model": base_settings.embedding_model_name,
            "top_k": settings.retrieval_top_k, "min_score": settings.rag_min_score,
            "python": platform.python_version(),
            "packages": {
                name: version(name) for name in ("qdrant-client", "fastembed", "langgraph")
            },
        },
        "counts": {"chunks": len(by_id), "questions": len(question_rows), "safety": len(risk_rows)},
        "metrics": metrics, "gate_thresholds": GATES, "gates": gates,
        "acceptance_passed": all(gates.values()), "questions": question_rows, "safety": risk_rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 合成测试集评估报告", "",
        f"生成时间（UTC）：{report['generated_at_utc']}",
        f"数据集：{report['dataset_version']}；配置：`{report['configuration']}`", "",
        f"样本数：{report['counts']}。验收门槛全部通过：**{report['acceptance_passed']}**。", "",
        "| 指标 | 测量值 |", "| --- | --- |",
    ]
    for name, value in report["metrics"].items():
        rendered = "N/A" if value is None else f"{value:.4f}"
        lines.append(f"| {name} | {rendered} |")
    lines += ["", "## 未达到的门槛", ""]
    lines += [
        f"- {name}: 要求 {report['gate_thresholds'].get(name, 0)}"
        for name, passed in report["gates"].items() if not passed
    ] or ["- 无"]
    lines += ["", "## 失败问答案例", ""]
    for row in report["questions"]:
        if "error" in row or (row["answerable"] and not row.get("cited_gold")) or (
            not row["answerable"] and not row.get("refused")
        ):
            predicted = row.get("answer", {}).get("mode", row.get("error"))
            lines.append(f"- `{row['id']}`：{row['query']} → {predicted}")
    lines += ["", "## 风险分级或路由不一致案例", ""]
    for row in report["safety"]:
        if not row["risk_correct"] or row["predicted_handoff"] != row["expected_handoff"]:
            lines.append(
                f"- `{row['id']}`：{row['query']}；"
                f"预期 {row['expected_risk']}/{row['expected_handoff']}，"
                f"实际 {row['predicted_risk']}/{row['predicted_handoff']}"
            )
    lines += [
        "", "## 解释边界", "",
        "这是固定的小型合成测试集，包含边界与挑战案例，不是独立真实客户测试集。",
        "引用完整性只验证来源 ID 与片段匹配，不能证明每个结论正确。",
        "grounded 是分数阈值标记，不证明证据足以回答问题；拒答按 no_evidence 模式严格统计。",
        "风险路由依据实际规则分类结果是否为 low 计算，与 Agent 条件边保持一致。",
        "不调用付费 LLM、不写业务数据库；只用真实本地 Embedding 和内存 Qdrant。",
        "耗时是模型预热后的 RAG 服务调用耗时，不含建索引、额外排名测量或 HTTP 开销。", "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/evaluation-latest.json")
    parser.add_argument("--check", action="store_true", help="指标未达预设门槛时退出码为 2。")
    args = parser.parse_args(argv)
    report = evaluate(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    args.output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"metrics": report["metrics"], "gates": report["gates"]}, ensure_ascii=True))
    print(f"Report: {args.output}")
    return 2 if args.check and not report["acceptance_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
