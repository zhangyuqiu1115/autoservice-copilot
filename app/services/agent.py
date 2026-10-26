"""用 LangGraph 编排售后分流；图中的节点不直接修改数据库。"""

from functools import lru_cache
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.models.enums import RiskLevel
from app.schemas.rag import RagCitationResponse
from app.services import rag
from app.services.safety import assess_risk
from app.services.vector_store import VectorStoreError


class AgentState(TypedDict):
    query: str
    document_id: int | None
    limit: int | None
    risk_level: RiskLevel
    issue_category: str
    risk_reason: str
    recommended_action: str
    grounded: bool
    citations: list[RagCitationResponse]
    execution_path: list[str]


def _assess(state: AgentState) -> dict[str, object]:
    assessment = assess_risk(state["query"])
    return {
        "risk_level": assessment.risk_level,
        "issue_category": assessment.issue_category,
        "risk_reason": assessment.reason,
        "execution_path": ["assess_risk"],
    }


def _route(state: AgentState) -> str:
    return "retrieve_answer" if state["risk_level"] == RiskLevel.LOW else "human_handoff"


def _retrieve_answer(state: AgentState) -> dict[str, object]:
    try:
        answer = rag.answer_question(
            state["query"],
            limit=state["limit"],
            document_id=state["document_id"],
        )
    except (rag.RagServiceError, VectorStoreError):
        return {
            "recommended_action": "知识服务暂不可用，已记录问题，等待售后人员处理。",
            "grounded": False,
            "citations": [],
            "execution_path": state["execution_path"] + ["retrieve_answer", "service_fallback"],
        }

    return {
        "recommended_action": answer.answer,
        "grounded": answer.grounded,
        "citations": [RagCitationResponse.model_validate(item) for item in answer.citations],
        "execution_path": state["execution_path"] + [
            "retrieve_answer",
            "evidence_found" if answer.grounded else "no_evidence",
        ],
    }


def _human_handoff(state: AgentState) -> dict[str, object]:
    if state["risk_level"] == RiskLevel.CRITICAL:
        action = (
            "描述涉及火烟等紧急风险，请优先远离危险区域并联系当地应急救援。"
            "本系统不提供现场维修指导，工单等待人工处理。"
        )
    else:
        action = "该问题需要售后专业人员确认，请联系授权服务中心，工单等待人工处理。"

    return {
        "recommended_action": action,
        "grounded": False,
        "citations": [],
        "execution_path": state["execution_path"] + ["human_handoff"],
    }


@lru_cache(maxsize=1)
def get_triage_graph() -> CompiledStateGraph:
    """编译无持久化副作用的有向状态图。"""

    graph = StateGraph(AgentState)
    graph.add_node("assess_risk", _assess)
    graph.add_node("retrieve_answer", _retrieve_answer)
    graph.add_node("human_handoff", _human_handoff)
    graph.add_edge(START, "assess_risk")
    graph.add_conditional_edges(
        "assess_risk",
        _route,
        {"retrieve_answer": "retrieve_answer", "human_handoff": "human_handoff"},
    )
    graph.add_edge("retrieve_answer", END)
    graph.add_edge("human_handoff", END)
    return graph.compile()


def triage_question(
    query: str,
    *,
    limit: int | None = None,
    document_id: int | None = None,
) -> AgentState:
    """执行图并返回建议；调用方负责一次性持久化结果。"""

    return get_triage_graph().invoke(
        {
            "query": query,
            "limit": limit,
            "document_id": document_id,
            "grounded": False,
            "citations": [],
            "execution_path": [],
        }
    )
