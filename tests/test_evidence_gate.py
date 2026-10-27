from typing import Any

import pytest

from app.core.config import Settings
from app.models.enums import RiskLevel
from app.services import rag, safety
from app.services.evidence_gate import supports_question
from app.services.vector_store import RetrievedChunk


@pytest.mark.parametrize(("query", "content", "supported"), [
    ("保修期限是几年？", "保修期限为3年。", True),
    ("How many years is the warranty?", "Warranty coverage lasts 2.5 years.", True),
    ("保修期具体多久？", "保修咨询请准备购车凭证。", False),
    ("保修期多久？", "保修资料登记购车日期为2023年。", False),
    ("保修期多久？", "保修年限没有说明。保养每2年一次。", False),
    ("空调滤芯多久检查？", "空调滤芯每8个月检查一次。", True),
    ("雨刷每几个月更换？", "雨刷保持清洁。保养间隔为6个月。", False),
    ("预约保养要多少钱？", "预约保养每次费用为120元。", True),
    ("预约保养要多少钱？", "预约保养请提供VIN和时间。", False),
    ("标称续航多少公里？", "标称续航为320公里。", True),
    ("标称续航多少公里？", "保修里程上限为100000公里。", False),
    ("我的车现在实际能跑多少公里？", "车辆标称续航为320公里。", False),
    ("建议胎压多少？", "建议胎压为230 kPa。", True),
    ("预约保养需要提供哪些资料？", "预约服务时提供VIN和希望到店的时间。", True),
    ("预约保养需要提供哪些资料？", "预约售后服务时可请工作人员检查空调滤芯。", False),
    ("What documents should I bring for warranty?", "申请保修时准备购车凭证。", True),
    ("蓝牙音响怎么连接？", "在蓝牙设置中选择连接音响。", True),
    ("明天天气怎么样？", "演示保养手册介绍车辆充电。", False),
])
def test_fact_requirements_and_topic_alignment(
    query: str, content: str, supported: bool,
) -> None:
    assert supports_question(query, content) is supported


@pytest.mark.parametrize(("question", "expected"), [
    ("充电座闻着有焦味", RiskLevel.HIGH),
    ("It smells burnt around the connector", RiskLevel.HIGH),
    ("车胎没气了，想去充电站", RiskLevel.HIGH),
    ("I have a punctured tire before charging", RiskLevel.HIGH),
    ("胎压偏低还可以去充电吗", RiskLevel.HIGH),
    ("Low tire pressure on the way to charging", RiskLevel.HIGH),
    ("充电口烫手", RiskLevel.MEDIUM),
    ("The connector is very hot", RiskLevel.MEDIUM),
    ("The cable is heating up quickly", RiskLevel.MEDIUM),
    ("电池位置有黑烟", RiskLevel.CRITICAL),
    ("The battery is smoldering", RiskLevel.CRITICAL),
    ("没有冒烟，我想看保养说明", RiskLevel.CRITICAL),
])
def test_hazard_synonyms_precede_routine_words(question: str, expected: RiskLevel) -> None:
    assert safety.assess_risk(question).risk_level == expected


def test_high_similarity_without_required_facts_refuses_before_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rag.vector_store, "search_document_chunks",
        lambda *args, **kwargs: [RetrievedChunk(1, 1, 0, "保修咨询准备购车凭证。", 0.99)],
    )
    settings = Settings(
        _env_file=None, rag_provider="openai_compatible",
        llm_base_url="http://localhost:11434/v1", llm_model="test-only",
    )

    def forbidden_call(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Unsupported evidence must not be forwarded to an LLM")

    monkeypatch.setattr(rag, "_generate_openai_compatible_answer", forbidden_call)
    result = rag.answer_question("保修几年？", settings=settings)
    assert result.mode == "no_evidence"
    assert result.grounded is False
    assert result.citations == []


def test_truncated_numeric_fact_cannot_support_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    content = "保修说明：" + "附加内容" * 200 + "。保修期限为4年。"
    monkeypatch.setattr(
        rag.vector_store, "search_document_chunks",
        lambda *args, **kwargs: [RetrievedChunk(1, 1, 0, content, 0.99)],
    )
    settings = Settings(_env_file=None, rag_max_context_chars=500)
    result = rag.answer_question("保修期限为几年？", settings=settings)
    assert result.mode == "no_evidence"


def test_missing_field_does_not_hide_supported_numeric_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rag.vector_store, "search_document_chunks",
        lambda *args, **kwargs: [
            RetrievedChunk(1, 1, 0, "保修咨询请带凭证。", 0.99),
            RetrievedChunk(2, 1, 1, "保修期限为3年。", 0.8),
        ],
    )
    result = rag.answer_question("保修几年？", settings=Settings(_env_file=None))
    assert result.grounded is True
    assert [item.chunk_id for item in result.citations] == [2]
    assert "3年" in result.answer
