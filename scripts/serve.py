"""先迁移数据库，再在同一进程启动单 worker API。"""

import argparse
import subprocess
import sys
from pathlib import Path

import uvicorn
from sqlalchemy.engine import make_url

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def prepare_directories(settings: Settings) -> None:
    for name in ("upload_directory", "qdrant_path", "embedding_cache_directory"):
        Path(getattr(settings, name)).mkdir(parents=True, exist_ok=True)
    url = make_url(settings.database_url)
    if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    prepare_directories(Settings())
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True,
    )
    # Qdrant Local Mode permits one writer per directory; do not add multiple workers.
    uvicorn.run("app.main:app", host=args.host, port=args.port, workers=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
