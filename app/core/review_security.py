"""本地演示的审核密钥，不替代生产环境的账号与角色系统。"""

from secrets import compare_digest
from typing import Annotated

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.core.config import get_settings

review_key_header = APIKeyHeader(
    name="X-Review-Key",
    scheme_name="ReviewKey",
    description="填写本地 REVIEW_API_KEY，仅用于审核和工单状态操作。",
    auto_error=False,
)


def require_review_key(
    key: Annotated[str | None, Security(review_key_header)],
) -> None:
    configured = get_settings().review_api_key
    if configured is None or not configured.get_secret_value().strip():
        raise HTTPException(status_code=503, detail="Human review is not configured.")
    expected = configured.get_secret_value()
    if key is None or not compare_digest(key.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=403, detail="Invalid review credentials.")
