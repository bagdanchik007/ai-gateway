"""Rate-Limiting-Middleware auf Basis von Redis (Fixed-Window-Zähler).

Zählt Requests pro Client (API-Key-Hash, sonst IP) in 60-Sekunden-Fenstern.
Läuft als HTTP-Middleware statt als FastAPI-Dependency, damit auch Requests
mit einem ungültigen Key mitgezählt werden — das erschwert Brute-Force auf
API-Keys zusätzlich zur eigentlichen Auth-Prüfung in app/api/deps.py.
"""

import hashlib
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.redis import get_redis

logger = structlog.get_logger(__name__)

_EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}
_WINDOW_SECONDS = 60


def _client_identifier(request: Request) -> str:
    """Bevorzugt den gehashten API-Key aus dem Authorization-Header, sonst die Client-IP.

    So teilen sich mehrere Clients hinter demselben NAT/Proxy nicht ein
    gemeinsames Limit, solange sie unterschiedliche Keys mitschicken. Der
    Klartext-Key landet dabei nie in Redis-Keys oder Logs — nur sein Hash.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
        return "key:" + hashlib.sha256(token.encode("utf-8")).hexdigest()

    client = request.client
    return "ip:" + (client.host if client else "unknown")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-Window-Rate-Limiting: max. N Requests pro angebrochener Minute.

    Fixed-Window statt Sliding-Window/Token-Bucket, weil es mit einem
    einzigen INCR+EXPIRE pro Request auskommt — für den Start bewusst
    einfach, bei Bedarf später gegen ein Sliding-Window austauschbar, ohne
    dass sich das Interface für aufrufenden Code ändert.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        settings = get_settings()
        limit = settings.rate_limit_requests_per_minute

        redis = get_redis()
        identifier = _client_identifier(request)
        window = int(time.time() // _WINDOW_SECONDS)
        key = f"ratelimit:{identifier}:{window}"

        count = await redis.incr(key)
        if count == 1:
            # Nur beim ersten Request im Fenster eine Expiry setzen — verhindert,
            # dass der Key durch jedes weitere incr() ohne Ablaufzeit bestehen bleibt.
            await redis.expire(key, _WINDOW_SECONDS)

        if count > limit:
            ttl = await redis.ttl(key)
            retry_after = max(ttl, 1)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "retry_after_seconds": retry_after},
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(limit - count, 0))
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Strukturiertes Logging pro Request: Methode, Pfad, Status, Dauer, Request-ID.

    Loggt bewusst keine Request-/Response-Bodies — die können Prompts und
    Completions enthalten, also sensible und teure Daten, die nicht
    versehentlich in einem Log-Aggregator landen sollen. Für Kosten-/
    Token-Details siehe stattdessen die UsageRecords (Commit 18).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else None,
        )
        return response
