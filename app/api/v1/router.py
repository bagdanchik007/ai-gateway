"""Aggregator für versionierte v1-Routen."""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.chat import router as chat_router
from app.api.v1.chat_ws import router as chat_ws_router
from app.api.v1.rag import router as rag_router

api_v1_router = APIRouter()

api_v1_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_v1_router.include_router(chat_ws_router, prefix="/chat", tags=["chat"])
api_v1_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_v1_router.include_router(rag_router, prefix="/rag", tags=["rag"])
