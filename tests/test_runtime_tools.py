from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from app.core.config import Settings
from scripts import local, serve, smoke


@pytest.mark.parametrize("value", [
    "https://example.com", "http://example.com", "http://127.0.0.1.evil.test",
    "http://user:password@localhost", "http://localhost/api", "http://localhost?key=secret",
])
def test_smoke_rejects_remote_or_ambiguous_targets(value: str) -> None:
    with pytest.raises(ValueError):
        smoke.validate_base_url(value)


@pytest.mark.parametrize("mode", ["create", "verify"])
def test_smoke_refuses_non_demo_api(mode: str) -> None:
    methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(200, json={"environment": "development"})

    with httpx.Client(
        base_url="http://127.0.0.1", transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(ValueError, match="ENVIRONMENT=demo"):
            if mode == "create":
                smoke.run_smoke(client, "test-only-key")
            else:
                smoke.verify_persisted_demo(client, "test-only-key", {"passed": True})
    assert methods == ["GET"]


def test_local_environment_is_separate_and_reuses_private_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(local, "Settings", lambda: Settings(_env_file=None, review_api_key=None))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///do-not-touch.db")
    first = local.prepare_environment(tmp_path / "demo")
    second = local.prepare_environment(tmp_path / "demo")
    assert first["REVIEW_API_KEY"] == second["REVIEW_API_KEY"]
    assert len(first["REVIEW_API_KEY"]) >= 40
    assert first["ENVIRONMENT"] == "demo"
    assert "do-not-touch.db" not in first["DATABASE_URL"]
    assert str(tmp_path) in first["QDRANT_PATH"]
    assert (tmp_path / "demo/.review-key").is_file()


def test_configured_review_key_is_not_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        local, "Settings", lambda: Settings(_env_file=None, review_api_key="existing-private-key"),
    )
    env = local.prepare_environment(tmp_path)
    assert env["REVIEW_API_KEY"] == "existing-private-key"
    assert not (tmp_path / ".review-key").exists()


def test_failed_migration_does_not_start_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(serve, "Settings", lambda: object())
    monkeypatch.setattr(serve, "prepare_directories", lambda settings: None)

    def failed_migration(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("migration failed")

    def forbidden_server(*args: Any, **kwargs: Any) -> None:
        pytest.fail("API must not start after a failed migration")

    monkeypatch.setattr(serve.subprocess, "run", failed_migration)
    monkeypatch.setattr(serve.uvicorn, "run", forbidden_server)
    with pytest.raises(RuntimeError, match="migration failed"):
        serve.main([])


def test_runtime_directories_include_sqlite_parent(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None, database_url=f"sqlite:///{(tmp_path / 'db/app.db').as_posix()}",
        upload_directory=str(tmp_path / "uploads"), qdrant_path=str(tmp_path / "vectors"),
        embedding_cache_directory=str(tmp_path / "models"),
    )
    serve.prepare_directories(settings)
    assert all((tmp_path / name).is_dir() for name in ("db", "uploads", "vectors", "models"))


def test_container_storage_and_build_context_exclude_private_data() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "compose.yaml").read_text(encoding="utf-8"))
    api = config["services"]["api"]
    assert all(port.startswith("127.0.0.1:") for port in api["ports"])
    assert "app-data:/app/data" in api["volumes"]
    assert api["read_only"] is True
    for name in ("QDRANT_PATH", "UPLOAD_DIRECTORY", "EMBEDDING_CACHE_DIRECTORY"):
        assert api["environment"][name].startswith("/app/data/")
    assert api["environment"]["DATABASE_URL"] == "sqlite:////app/data/autoservice.db"
    assert api["environment"]["REVIEW_API_KEY"].startswith("${REVIEW_API_KEY:?")
    excluded = (root / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert all(name in excluded for name in (".env", ".git", ".venv", "data", "*.db"))
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "USER 10001:10001" in dockerfile
    assert "COPY . ." not in dockerfile
