"""一键运行使用独立演示数据的本地 API。"""

import argparse
import os
import secrets
from pathlib import Path

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data/private/local-demo"


def prepare_environment(data_directory: Path) -> dict[str, str]:
    settings = Settings()
    directory = data_directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    configured_key = settings.review_api_key
    key_file = directory / ".review-key"
    if configured_key is not None and configured_key.get_secret_value().strip():
        key = configured_key.get_secret_value()
    elif key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
        if not key:
            raise ValueError("The local review key file is empty.")
    else:
        key = secrets.token_urlsafe(32)
        with key_file.open("x", encoding="utf-8") as stream:
            stream.write(key + "\n")
        if os.name != "nt":
            key_file.chmod(0o600)

    model_cache = Path(settings.embedding_cache_directory)
    if not model_cache.is_absolute():
        model_cache = ROOT / model_cache
    return {
        "ENVIRONMENT": "demo", "DEBUG": "false", "API_PREFIX": "/api/v1",
        "DATABASE_URL": f"sqlite:///{(directory / 'autoservice.db').as_posix()}",
        "UPLOAD_DIRECTORY": str(directory / "uploads"),
        "QDRANT_PATH": str(directory / "qdrant"),
        "EMBEDDING_CACHE_DIRECTORY": str(model_cache.resolve()),
        "REVIEW_API_KEY": key, "RAG_PROVIDER": "extractive",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    os.chdir(ROOT)
    os.environ.update(prepare_environment(args.data_dir))
    print(f"Demo data: {args.data_dir.resolve()}", flush=True)
    print(f"Swagger: http://127.0.0.1:{args.port}/docs", flush=True)
    print("Review key: private .env/environment or demo .review-key file.", flush=True)
    from scripts.serve import main as serve_main

    return serve_main(["--host", "127.0.0.1", "--port", str(args.port)])


if __name__ == "__main__":
    raise SystemExit(main())
