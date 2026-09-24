from enum import StrEnum


class PowertrainType(StrEnum):
    """车辆动力类型。"""

    BEV = "bev"
    PHEV = "phev"
    EREV = "erev"
    HEV = "hev"


class DocumentType(StrEnum):
    """售后知识库文档类型。"""

    OWNER_MANUAL = "owner_manual"
    SERVICE_MANUAL = "service_manual"
    WARRANTY_POLICY = "warranty_policy"
    SERVICE_BULLETIN = "service_bulletin"
    FAQ = "faq"


class ProcessingStatus(StrEnum):
    """文档进入 RAG 知识库时的处理状态。"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(StrEnum):
    """售后问题的风险等级。"""

    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(StrEnum):
    """售后工单状态。"""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    CLOSED = "closed"