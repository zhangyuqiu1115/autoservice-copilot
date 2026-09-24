from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# SQLite 默认只允许创建连接的线程使用该连接。
# FastAPI 可能在线程池中处理同步接口，因此需要关闭该限制。
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """为每次 API 请求提供一个数据库会话，并在结束后关闭它。"""

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()