"""Admin-Endpoints: API-Key-Verwaltung und Usage-Statistik.

Alle Routen hier verlangen `Depends(get_current_admin_user)` — bewusst
getrennt von der normalen Chat-API-Auth, damit ein kompromittierter
normaler API-Key keinen Zugriff auf fremde Keys oder Statistiken gibt.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin_user
from app.core.security import generate_api_key
from app.db.models.api_key import APIKey
from app.db.models.usage_record import UsageRecord
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.admin import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyOut,
    UsageByModel,
    UsageStatsOut,
)

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


async def _get_or_create_user(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=email)
        db.add(user)
        await db.flush()  # Damit user.id für den neuen APIKey verfügbar ist, ohne schon zu committen
    return user


@router.post(
    "/api-keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Neuen API-Key erzeugen (legt den User bei Bedarf an)",
)
async def create_api_key(
    body: APIKeyCreateRequest, db: AsyncSession = Depends(get_db)
) -> APIKeyCreateResponse:
    user = await _get_or_create_user(db, body.user_email)

    plain_key, key_hash, key_prefix = generate_api_key()
    api_key = APIKey(
        user_id=user.id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        expires_at=body.expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return APIKeyCreateResponse(id=api_key.id, key=plain_key, key_prefix=key_prefix)


@router.get("/api-keys", response_model=list[APIKeyOut], summary="Alle API-Keys auflisten")
async def list_api_keys(db: AsyncSession = Depends(get_db)) -> list[APIKeyOut]:
    result = await db.execute(
        select(APIKey).options(selectinload(APIKey.user)).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        APIKeyOut(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            user_email=k.user.email,
            is_active=k.is_active,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            expires_at=k.expires_at,
        )
        for k in keys
    ]


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="API-Key widerrufen (soft delete, nicht gelöscht)",
)
async def revoke_api_key(key_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Setzt is_active=False statt den Datensatz zu löschen.

    So bleiben zugehörige UsageRecords (siehe Commit 18) über den FK
    weiterhin referenzierbar, und der Key kann bei Bedarf wieder aktiviert werden.
    """
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API-Key nicht gefunden")

    api_key.is_active = False
    await db.commit()


@router.get("/usage", response_model=UsageStatsOut, summary="Aggregierte Usage-Statistik")
async def get_usage_stats(db: AsyncSession = Depends(get_db)) -> UsageStatsOut:
    by_model_result = await db.execute(
        select(
            UsageRecord.provider,
            UsageRecord.model,
            func.count(UsageRecord.id).label("request_count"),
            func.sum(UsageRecord.total_tokens).label("total_tokens"),
            func.sum(UsageRecord.cost_usd).label("total_cost_usd"),
        ).group_by(UsageRecord.provider, UsageRecord.model)
    )
    by_model = [
        UsageByModel(
            provider=row.provider,
            model=row.model,
            request_count=row.request_count,
            total_tokens=row.total_tokens or 0,
            total_cost_usd=float(row.total_cost_usd or 0),
        )
        for row in by_model_result.all()
    ]

    return UsageStatsOut(
        total_requests=sum(m.request_count for m in by_model),
        total_tokens=sum(m.total_tokens for m in by_model),
        total_cost_usd=round(sum(m.total_cost_usd for m in by_model), 6),
        by_model=by_model,
    )
