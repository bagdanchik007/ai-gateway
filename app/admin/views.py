"""SQLAdmin-ModelViews für die zentralen Tabellen.

Bewusste Einschränkungen pro View: API-Keys werden ausschließlich über
POST /api/v1/admin/api-keys erzeugt (dort wird Hash+Prefix korrekt gesetzt,
siehe app/core/security.py) — im Panel deshalb nicht erstellbar, und der
Hash selbst ist nie editier- oder auch nur sichtbar. UsageRecords sind
reine Audit-Daten und daher komplett read-only.
"""

from sqladmin import ModelView

from app.db.models.api_key import APIKey
from app.db.models.usage_record import UsageRecord
from app.db.models.user import User


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    column_list = [User.id, User.email, User.is_active, User.is_admin, User.created_at]
    column_searchable_list = [User.email]
    column_sortable_list = [User.email, User.created_at]


class APIKeyAdmin(ModelView, model=APIKey):
    name = "API Key"
    name_plural = "API Keys"
    icon = "fa-solid fa-key"
    column_list = [
        APIKey.id,
        APIKey.name,
        APIKey.key_prefix,
        APIKey.user,
        APIKey.is_active,
        APIKey.created_at,
        APIKey.last_used_at,
    ]
    column_searchable_list = [APIKey.name, APIKey.key_prefix]
    form_columns = [APIKey.name, APIKey.is_active, APIKey.expires_at]  # kein key_hash im Formular
    can_create = False  # Erzeugung nur über POST /api/v1/admin/api-keys (setzt Hash+Prefix korrekt)


class UsageRecordAdmin(ModelView, model=UsageRecord):
    name = "Usage Record"
    name_plural = "Usage Records"
    icon = "fa-solid fa-chart-line"
    column_list = [
        UsageRecord.id,
        UsageRecord.provider,
        UsageRecord.model,
        UsageRecord.total_tokens,
        UsageRecord.cost_usd,
        UsageRecord.created_at,
    ]
    column_sortable_list = [UsageRecord.created_at, UsageRecord.cost_usd]
    can_create = False
    can_edit = False
    can_delete = False
