"""Zentrale Registrierung aller ORM-Modelle.

Wird von alembic/env.py per `from app.db.models import *` importiert, damit
Base.metadata alle Tabellen kennt (nötig für `alembic revision --autogenerate`).
Neue Modelle müssen hier immer ergänzt werden.
"""

from app.db.models.api_key import APIKey
from app.db.models.usage_record import UsageRecord
from app.db.models.user import User

__all__ = ["User", "APIKey", "UsageRecord"]
