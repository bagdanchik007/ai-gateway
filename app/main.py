"""Einstiegspunkt der FastAPI-Anwendung.

Die Datei ist bewusst schlank: sie erstellt die App, bindet Router ein und
verwaltet den Lifespan. Die gesamte Business-Logik lebt in app/services und
app/providers, nicht hier — main.py soll nicht mit jeder neuen Roadmap-Etappe
wachsen.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import get_settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("app_startup", app_env=settings.app_env, debug=settings.app_debug)
    yield
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    """Factory statt eines nackten Modul-`app = FastAPI()`.

    So kann die App mehrfach mit unterschiedlicher Konfiguration erstellt
    werden — das wird für Tests benötigt (eigene Test-DB/Settings pro Lauf),
    ohne Seiteneffekte durch den Modul-Import.
    """
    settings = get_settings()

    app = FastAPI(
        title="AI Gateway",
        description=(
            "Multi-provider LLM gateway: routing with fallback, usage tracking, "
            "API-key auth and an OpenAI-compatible Chat Completions API."
        ),
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix="/api/v1")

    return app


app = create_app()
