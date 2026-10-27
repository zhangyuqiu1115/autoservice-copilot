"""可审计的售后演示规则；无法识别的描述交由人工判断。"""

import re
from dataclasses import dataclass

from app.models.enums import RiskLevel


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    risk_level: RiskLevel
    issue_category: str
    reason: str


# 从最高等级开始匹配；保守处理提问、否定句和历史描述中的风险词。
# 这些规则只控制流程分流，不用于车辆诊断或安全认证。
RULES: tuple[tuple[RiskLevel, str, str], ...] = (
    (
        RiskLevel.CRITICAL,
        "fire_or_smoke",
        r"冒烟|浓烟|白烟|黑烟|烟雾|起火|着火|自燃|火焰|爆炸|热失控|"
        r"\b(smoke|smoking|fire|flames?|explosion|smouldering|smoldering)\b",
    ),
    (
        RiskLevel.HIGH,
        "braking_or_steering",
        r"刹车|制动|转向|方向盘|\b(brakes?|braking|steering)\b",
    ),
    (
        RiskLevel.HIGH,
        "high_voltage_or_collision",
        r"漏电|触电|高压|电池鼓包|电池漏液|碰撞|撞车|"
        r"\b(high[ -]?voltage|electric shock|collision|crash|swollen battery)\b",
    ),
    (
        RiskLevel.HIGH,
        "burning_smell_or_tire_pressure_loss",
        r"烧焦|焦糊|焦味|爆胎|(?:轮胎|车胎).{0,8}(?:漏气|没气|瘪|破裂)|"
        r"胎压.{0,6}(?:下降|降低|不足|偏低|过低|报警)|"
        r"\b(?:burning|burnt|scorched)\s+(?:smell|odou?r)|"
        r"\bsmell\w*.{0,24}(?:burning|burnt|scorched)|"
        r"\b(?:tyre|tire).{0,24}(?:flat|deflat|punctur|leak|losing air|air loss|blowout)|"
        r"\b(?:flat|deflat\w*|punctur\w*).{0,16}(?:tyre|tire)\b|"
        r"\blow\s+(?:tyre|tire)\s+pressure\b",
    ),
    (
        RiskLevel.MEDIUM,
        "charging_or_fault",
        r"无法充电|充不进|充电失败|异响|异味|过热|烫手|发热|高温|"
        r"故障|无法启动|损坏|报警|异常|失灵|失效|"
        r"\b(overheat\w*|warning light|charging fail\w*|cannot charge|won't start|"
        r"fault\w*|broken|damag\w*|(?:very|extremely|too|unusually)\s+hot|"
        r"heating\s+up|hot\s+to\s+(?:touch|handle))\b",
    ),
    (
        RiskLevel.LOW,
        "routine_information",
        r"保养|保修|手册|说明书|充电|续航|雨刷|空调|"
        r"\b(maintenance|warranty|manual|charging|range|wipers?|air conditioning)\b",
    ),
)


def assess_risk(question: str) -> RiskAssessment:
    """优先匹配高风险词，未命中已知例行场景则保持 unknown。"""

    question = " ".join(question.split())
    for level, category, pattern in RULES:
        if re.search(pattern, question, flags=re.IGNORECASE):
            return RiskAssessment(
                risk_level=level,
                issue_category=category,
                reason=f"规则匹配：{category}；仅用于初步分流，待人工确认。",
            )

    return RiskAssessment(
        risk_level=RiskLevel.UNKNOWN,
        issue_category="unclassified",
        reason="描述未命中已知例行问题规则，风险待人工确认。",
    )
