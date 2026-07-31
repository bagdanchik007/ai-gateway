"""Bindet das SQLAdmin-Panel an die FastAPI-App (siehe app/main.py)."""

from fastapi import FastAPI
from sqladmin import Admin

from app.admin.auth import AdminPanelAuth
from app.admin.views import APIKeyAdmin, UsageRecordAdmin, UserAdmin
from app.core.config import get_settings
from app.db.session import engine


def setup_admin_panel(app: FastAPI) -> None:
    settings = get_settings()
    admin = Admin(
        app,
        engine,
        authentication_backend=AdminPanelAuth(secret_key=settings.secret_key.get_secret_value()),
        base_url="/admin-panel",
    )
    admin.add_view(UserAdmin)
    admin.add_view(APIKeyAdmin)
    admin.add_view(UsageRecordAdmin)