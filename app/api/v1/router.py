"""Aggregator für versionierte v1-Routen.

Einzelne Domain-Router (auth, chat, admin, usage usw.) werden hier nach und
nach in den folgenden Etappen eingebunden — das ist die einzige Stelle, die
beim Hinzufügen eines neuen API-Moduls angefasst werden muss. app/main.py
bleibt dabei stabil.
"""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.chat import router as chat_router

api_v1_router = APIRouter()

api_v1_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_v1_router.include_router(admin_router, prefix="/admin", tags=["admin"])
