"""Alembic-Umgebung für async SQLAlchemy.

Zwei Abweichungen vom Standard-Template:
1. `target_metadata` zeigt auf `app.db.base.Base.metadata` — Modelle werden
   importiert, damit Alembic sie für `--autogenerate` sieht.
2. Die DB-URL kommt aus unseren pydantic-settings (also aus .env), nicht aus
   `sqlalchemy.url` in alembic.ini. Ein Secret gehört nicht in eine
   eingecheckte .ini-Datei.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from app.core.config import get_settings
from app.db.base import Base

# Modell-Importe: müssen hier geschehen, damit Base.metadata alle Tabellen kennt.
from app.db.models import *  # noqa: F401,F403
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
