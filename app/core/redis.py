"""Async Redis-Client als Singleton.

Ein Connection-Pool pro Prozess (redis-py verwaltet das Pooling intern, ein
erneutes `from_url` pro Request wäre unnötig teuer). Wird aktuell fürs Rate
Limiting genutzt, später auch für Caching und Usage-Counter (Etappe 4).
"""

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    """Liefert den Prozess-weiten Redis-Client (lazy erzeugt, wiederverwendet)."""
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    """Wird im Lifespan-Shutdown aufgerufen, um den Connection-Pool sauber zu schließen."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
