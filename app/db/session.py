"""Async DB-Engine und Session-Factory.

Ein einziger Engine pro Prozess (SQLAlchemy übernimmt Connection Pooling
intern). `get_db` ist eine FastAPI-Dependency, die pro Request eine Session
liefert und bei einer Exception zuverlässig zurückrollt — so bleibt die DB
nie mit einer halbfertigen Transaktion eines fehlgeschlagenen Requests zurück.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    pool_pre_ping=True,  # verhindert "server closed the connection unexpectedly" nach Idle-Timeouts
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,  # ORM-Objekte bleiben nach commit() nutzbar (z. B. für Response-Serialisierung)
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI-Dependency: liefert eine DB-Session pro Request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
