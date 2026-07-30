"""Usage-Tracking.

Persistiert nach jeder abgeschlossenen Chat-Completion (Stream oder nicht)
einen UsageRecord — Grundlage für Kosten-Reporting und die Admin-Endpoints
(Etappe 4, Commit 20).
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.usage_record import UsageRecord
from app.services.cost_calculator import calculate_cost_usd

logger = structlog.get_logger(__name__)


async def record_usage(
    db: AsyncSession,
    api_key_id: uuid.UUID | None,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> UsageRecord:
    """Speichert einen Usage-Record. Ein Fehler hier darf die Chat-Antwort nicht gefährden.

    Deshalb fängt der aufrufende Code (app/api/v1/chat.py) etwaige Exceptions
    ab und loggt sie nur — der Nutzer soll seine Antwort auch dann bekommen,
    wenn das Usage-Tracking selbst mal einen DB-Hänger hat.
    """
    cost = calculate_cost_usd(provider, model, prompt_tokens, completion_tokens)
    record = UsageRecord(
        api_key_id=api_key_id,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        cost_usd=cost,
    )
    db.add(record)
    await db.commit()
    logger.info(
        "usage.recorded",
        provider=provider,
        model=model,
        total_tokens=record.total_tokens,
        cost_usd=cost,
    )
    return record
