from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Manage resources when the API starts and stops."""

    application.state.ready = True
    yield
    application.state.ready = False


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    application.include_router(
        health_router,
        prefix=settings.api_prefix,
    )

    @application.get("/", tags=["root"])
    def root() -> dict[str, str]:
        return {
            "message": "AutoService Copilot API is running.",
            "documentation": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    return application


app = create_app()