"""抽取型回答的保守事实覆盖检查；不是通用的语义蕴含模型。"""

import re

from app.services.vector_store import RetrievedChunk

# 主题优先级处理复合问题：例如“充满电能跑几公里”优先检查续航事实。
TOPICS = (
    r"保修|质保|warrant\w*|coverage",
    r"预约|约.{0,4}售后|appointment|booking|book.{0,16}(?:service|maintenance)",
    r"续航|跑.{0,8}(?:公里|千米)|driving range|rated range|\brange\b|how far",
    r"空调滤芯|空调滤清器|cabin filter|air.{0,12}filter",
    r"雨刷|雨刮|wipers?",
    r"胎压|气压|轮胎|车胎|tyres?|tires?",
    r"充电|充电枪|charging|charge port|connector|plugging",
)
NUMBER = r"(?:\d+(?:\.\d+)?|[零一二三四五六七八九十百千万两]+|one|two|three|four|five|six)"
QUANTITIES = (
    (
        r"多少.{0,4}(?:公里|千米|km)|几公里|(?:续航|里程).{0,8}(?:多少|几)|"
        r"how far|how many (?:miles|kilometers)|what.{0,16}(?:rated|driving|remaining)\s+range",
        rf"{NUMBER}\s*(?:公里|千米|km\b|kilomet(?:er|re)s?\b|miles?\b)",
        "distance",
    ),
    (
        r"几年|几(?:个)?月|多少.{0,4}(?:年|月|天|周|小时)|多久|多长时间|"
        r"how (?:many years|many months|many days|long|often)",
        rf"{NUMBER}\s*(?:年|个月|月|天|周|小时|years?\b|months?\b|days?\b|hours?\b)",
        "time",
    ),
    (
        r"(?:胎压|气压).{0,8}(?:多少|几)|多少.{0,4}(?:kpa|bar|psi)|what.{0,16}pressure",
        rf"{NUMBER}\s*(?:kpa\b|bar\b|psi\b|千帕)",
        "pressure",
    ),
    (
        r"多少钱|费用.{0,6}多少|收费.{0,6}多少|how much.{0,24}(?:cost|fee|pay)|"
        r"(?:price|fee|cost).{0,8}(?:\?|多少)",
        rf"(?:{NUMBER}\s*(?:元|块|美元|dollars?|aud|cny|usd)|[$￥¥]\s*\d+)",
        "money",
    ),
)
UNSPECIFIED = (
    r"未(?:规定|提供|说明|给出)|不(?:提供|包含|预测)|没有(?:规定|提供|说明)|"
    r"不能(?:预测|承诺|保证)|not (?:specified|provided)|"
    r"(?:does not|doesn't|cannot|can't).{0,16}(?:specify|provide|predict|guarantee)"
)
INFO_QUESTION = (
    r"(?:哪些|什么).{0,5}(?:信息|材料|凭证|资料)|(?:需要|要).{0,8}(?:哪些|什么).{0,6}带|"
    r"(?:which|what).{0,30}(?:details|documents)|what.{0,20}(?:provide|bring|prepare)"
)
PROVIDES_INFO = r"提供|准备|携带|提交|带上|请带|provide|bring|prepare|submit"
INFO_FIELDS = (
    r"vin|里程|日期|凭证|票据|行驶证|身份证|车牌|时间|联系方式|mileage|certificate|documents?"
)
STOP_WORDS = {
    "what", "which", "where", "when", "how", "should", "would", "could", "with", "this",
    "that", "does", "have", "need", "the", "and", "for", "are", "can", "you", "your",
    "什么", "怎么", "多少", "哪里", "可以", "需要", "应该", "资料", "信息", "具体",
}


def _matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _sentences(content: str) -> list[str]:
    # Preserve decimal values such as 2.5 years.
    return re.split(r"[。！？!?\n]|(?<!\d)\.(?!\d)", content)


def _lexical_overlap(query: str, content: str) -> bool:
    tokens = set(re.findall(r"[a-z]{3,}", query.lower())) - STOP_WORDS
    for segment in re.findall(r"[\u4e00-\u9fff]+", query):
        tokens.update(segment[index:index + 2] for index in range(len(segment) - 1))
    tokens -= STOP_WORDS
    return sum(token in content.lower() for token in tokens) >= 2


def supports_question(query: str, content: str) -> bool:
    """要求主题覆盖；数量问题还需同一相关句中出现可引用的数量事实。"""

    topic = next((pattern for pattern in TOPICS if _matches(pattern, query)), None)
    sentences = [text for text in _sentences(content) if text.strip()]
    if topic is not None:
        sentences = [text for text in sentences if _matches(topic, text)]
    elif not _lexical_overlap(query, content):
        return False
    if not sentences:
        return False

    quantity = next((item for item in QUANTITIES if _matches(item[0], query)), None)
    if quantity is not None:
        _, value_pattern, kind = quantity
        if kind == "distance" and _matches(
            r"现在|当前|此刻|实际|actual|current|remaining|right now", query,
        ):
            # Static manuals cannot establish a specific vehicle's live driving range.
            return False
        return any(
            _matches(value_pattern, text)
            and not _matches(UNSPECIFIED, text)
            and not (kind == "time" and _matches(r"购车日期|登记日期|purchase date", text))
            for text in sentences
        )

    if _matches(INFO_QUESTION, query):
        return any(
            _matches(PROVIDES_INFO, text) and _matches(INFO_FIELDS, text)
            and not _matches(UNSPECIFIED, text)
            for text in sentences
        )
    return True


def filter_supporting_evidence(
    query: str, chunks: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    return [chunk for chunk in chunks if supports_question(query, chunk.content)]
