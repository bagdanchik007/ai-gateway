"""FastAPI-Dependencies für Authentifizierung.

Ablauf: Bearer-Token aus dem Authorization-Header lesen -> Hash bilden ->
in der DB nachschlagen -> Aktiv-/Ablauf-Status prüfen -> last_used_at
aktualisieren -> APIKey (bzw. den zugehörigen User) zurückgeben.

Jeder geschützte Endpoint hängt einfach `Depends(get_current_api_key)` oder
`Depends(get_current_user)` an — die DB-Lookup-Logik lebt nur hier.
"""

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_api_key
from app.db.models.api_key import APIKey
from app.db.models.user import User
from app.db.session import get_db

# auto_error=False: wir werfen die 401 selbst, damit wir konsistente
# WWW-Authenticate-Header und Fehlermeldungen im ganzen Projekt garantieren können.
_bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing API key",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    """Validiert den API-Key aus `Authorization: Bearer <key>` und gibt ihn zurück."""
    if credentials is None:
        raise _UNAUTHORIZED

    key_hash = hash_api_key(credentials.credentials)

    result = await db.execute(
        select(APIKey)
        # eager laden, weil api_key.user in async-Kontext sonst nicht sicher
        # nachträglich lazy geladen werden kann (kein impliziter await möglich)
        .options(selectinload(APIKey.user))
        .where(APIKey.key_hash == key_hash)
    )
    api_key = result.scalar_one_or_none()

    if api_key is None or not api_key.is_active or not api_key.user.is_active:
        raise _UNAUTHORIZED

    if api_key.expires_at is not None and api_key.expires_at < datetime.now(UTC):
        raise _UNAUTHORIZED

    api_key.last_used_at = datetime.now(UTC)
    await db.commit()

    return api_key


async def get_current_user(api_key: APIKey = Depends(get_current_api_key)) -> User:
    """Convenience-Dependency für Endpoints, die nur den User brauchen, nicht den Key selbst."""
    return api_key.user
