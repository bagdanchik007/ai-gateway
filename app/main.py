"""Einstiegspunkt der FastAPI-Anwendung."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.admin import setup_admin_panel
from app.api.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from app.core.redis import close_redis

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("app_startup", app_env=settings.app_env, debug=settings.app_debug)
    yield
    await close_redis()
    logger.info("app_shutdown")


_TAGS_METADATA = [
    {"name": "infra", "description": "Liveness/Readiness-Check."},
    {"name": "chat", "description": "OpenAI-kompatible Chat Completions."},
    {"name": "admin", "description": "Verwaltung von API-Keys und Usage-Statistiken."},
]


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title="AI Gateway",
        description="Multi-provider LLM Gateway.",
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
        openapi_tags=_TAGS_METADATA,
        contact={"name": "Bohdan Skibitskyi", "url": "https://github.com/bagdanchik007/ai-gateway"},
        license_info={"name": "MIT"},
    )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix="/api/v1")

    setup_admin_panel(app)

    # Minimale statische Demo-UI zum interaktiven Ausprobieren der API — kein
    # Build-Schritt, kein SPA-Framework, bewusst einfach gehalten. Unter
    # /app (nicht /) gemountet, damit die Wurzel für zukünftige eigene
    # Zwecke frei bleibt und nicht mit /api, /docs, /admin-panel kollidiert.
    app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")

    return app


app = create_app()
