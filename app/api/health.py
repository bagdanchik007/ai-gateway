"""Infrastruktur-Endpunkte (Liveness/Readiness).

Bewusst außerhalb von /api/v1: der Health-Check ist ein Vertrag mit dem
Orchestrator (Docker/K8s) und kein Teil der Business-API — er sollte nicht
zusammen mit ihr versioniert werden.
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["infra"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_env: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Liveness/readiness probe")
async def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", app_env=settings.app_env, version="0.1.0")
