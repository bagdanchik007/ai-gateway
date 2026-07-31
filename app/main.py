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
    {
        "name": "infra",
        "description": "Liveness/Readiness-Check für Orchestratoren (Docker/K8s). Kein Auth nötig.",
    },
    {
        "name": "chat",
        "description": (
            "OpenAI-kompatible Chat Completions. Erfordert `Authorization: Bearer <api-key>`. "
            "Unterstützt Streaming (SSE), providerübergreifendes Fallback, serverseitige "
            "Chat-Historie (`conversation_id`) und automatisches Usage-Tracking."
        ),
    },
    {
        "name": "admin",
        "description": (
            "Verwaltung von API-Keys und Usage-Statistiken. Erfordert einen API-Key eines "
            "Users mit `is_admin=true` — getrennt von der normalen Chat-Auth."
        ),
    },
]


def create_app() -> FastAPI:
    """Factory statt eines nackten Modul-`app = FastAPI()`.

    So kann die App mehrfach mit unterschiedlicher Konfiguration erstellt
    werden — das wird für Tests benötigt (eigene Test-DB/Settings pro Lauf),
    ohne Seiteneffekte durch den Modul-Import.
    """
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title="AI Gateway",
        description=(
            "Multi-provider LLM Gateway: Routing mit Fallback, Usage-Tracking, "
            "API-Key-Auth und eine OpenAI-kompatible Chat Completions API.\n\n"
            "Alle `/api/v1/chat/*`- und `/api/v1/admin/*`-Endpoints erfordern den Header "
            "`Authorization: Bearer <api-key>`. Über den 'Authorize'-Button oben rechts "
            "kann ein Key für alle Requests in dieser Swagger-UI hinterlegt werden."
        ),
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
        openapi_tags=_TAGS_METADATA,
        contact={"name": "Bohdan Skibitskyi", "url": "https://github.com/bagdanchik007/ai-gateway"},
        license_info={"name": "MIT"},
    )

    app.add_middleware(RateLimitMiddleware)
    # Zuletzt hinzugefügt = äußerste Schicht: umschließt auch die vom
    # RateLimitMiddleware früh zurückgegebenen 429-Antworten, damit wirklich
    # jeder Request geloggt wird, nicht nur die, die den Handler erreichen.
    app.add_middleware(RequestLoggingMiddleware)

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix="/api/v1")

    setup_admin_panel(app)

    return app


app = create_app()
