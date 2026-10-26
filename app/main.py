from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.agent import router as agent_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.rag import router as rag_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.service_tickets import router as service_tickets_router
from app.api.routes.vehicles import router as vehicles_router
from app.core.config import get_settings
from app.services import (
    vector_store as vector_store_service,
)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Manage resources when the API starts and stops."""

    application.state.ready = True

    try:
        yield
    finally:
        vector_store_service.close_qdrant_client()
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

    application.include_router(
        vehicles_router,
        prefix=settings.api_prefix,
    )

    application.include_router(
        documents_router,
        prefix=settings.api_prefix,
    )

    application.include_router(
        retrieval_router,
        prefix=settings.api_prefix,
    )

    application.include_router(
        rag_router,
        prefix=settings.api_prefix,
    )

    @application.get("/", tags=["root"])
    def root() -> dict[str, str]:
        return {
            "message": "AutoService Copilot API is running.",
            "documentation": "/docs",
            "health": f"{settings.api_prefix}/health",
            "vehicles": f"{settings.api_prefix}/vehicles",
            "documents": f"{settings.api_prefix}/documents",
            "retrieval": f"{settings.api_prefix}/retrieval/search",
            "rag": f"{settings.api_prefix}/rag/answer",
            "agent": f"{settings.api_prefix}/agent/triage",
            "service_tickets": f"{settings.api_prefix}/service-tickets",
        }

    application.include_router(agent_router, prefix=settings.api_prefix)
    application.include_router(service_tickets_router, prefix=settings.api_prefix)

    return application


app = create_app()
