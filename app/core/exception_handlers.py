"""Globale Exception-Handler für konsistente Fehlerantworten.

Jeder Fehler wird im gleichen Format ausgeliefert:
`{"error": {"message": ..., "type": ..., "status_code": ...}}`
— unabhängig davon, ob er von einem ProviderError, einer Pydantic-
Validierung, einer expliziten HTTPException oder einer unerwarteten
Exception stammt. Das macht clientseitiges Error-Handling einheitlich,
angelehnt an das Format der OpenAI-API.

Nur für den Non-Stream-Pfad relevant: sobald bei Streaming-Antworten der
200-Header einmal gesendet ist, kann kein HTTP-Statuscode mehr geändert
werden — dort greift stattdessen das Inline-Error-Event in
app/api/v1/chat.py (_sse_stream).
"""

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.providers.exceptions import (
    ModelNotFoundError,
    ProviderAuthenticationError,
    ProviderError,
)
from app.services.llm_router import NoProviderAvailableError

logger = structlog.get_logger(__name__)


def _error_response(status_code: int, message: str, error_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": error_type, "status_code": status_code}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc.errors()), "validation_error"
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return _error_response(exc.status_code, str(exc.detail), "http_error")

    # Spezifischere Handler zuerst registrieren: FastAPI matcht bei mehreren
    # passenden Exception-Handlern den zur konkretesten Klasse in der MRO.
    @app.exception_handler(ProviderAuthenticationError)
    async def provider_auth_handler(
        request: Request, exc: ProviderAuthenticationError
    ) -> JSONResponse:
        # Der *Provider*-Key ist ungültig (Server-Fehlkonfiguration), nicht der
        # API-Key des Aufrufers — daher 502, nicht 401.
        return _error_response(
            status.HTTP_502_BAD_GATEWAY, str(exc), "provider_authentication_error"
        )

    @app.exception_handler(ModelNotFoundError)
    async def model_not_found_handler(request: Request, exc: ModelNotFoundError) -> JSONResponse:
        return _error_response(status.HTTP_404_NOT_FOUND, str(exc), "model_not_found")

    @app.exception_handler(NoProviderAvailableError)
    async def no_provider_handler(
        request: Request, exc: NoProviderAvailableError
    ) -> JSONResponse:
        return _error_response(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc), "no_provider_available")

    @app.exception_handler(ProviderError)
    async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
        return _error_response(status.HTTP_502_BAD_GATEWAY, str(exc), "provider_error")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Bewusst keine exc-Details an den Client — könnten interne Pfade,
        # Connection-Strings o. Ä. enthalten. Der vollständige Traceback geht
        # ins Log (siehe exc_info), der Client bekommt nur eine generische Meldung.
        logger.error(
            "unhandled_exception", error=str(exc), path=request.url.path, exc_info=exc
        )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error", "internal_error"
        )
