"""Authentifizierung für das SQLAdmin-Panel.

Das Gateway selbst hat kein Passwort-Login (nur API-Keys, siehe
app/core/security.py). Für dieses interne Betreiber-Panel reicht ein
einzelnes geteiltes Passwort aus den Settings — kein User-spezifischer
Login, keine Rollen. Gedacht für den Einsatz hinter einem internen
Netz/VPN, nicht als öffentlich erreichbare Login-Seite.
"""

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.core.config import get_settings


class AdminPanelAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        password = form.get("password")
        settings = get_settings()

        if settings.admin_panel_secret is None:
            # Kein Secret konfiguriert -> Panel bewusst unzugänglich statt
            # eines unsicheren Default-Passworts.
            return False

        if password == settings.admin_panel_secret.get_secret_value():
            request.session.update({"admin_panel_authenticated": True})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("admin_panel_authenticated", False))
