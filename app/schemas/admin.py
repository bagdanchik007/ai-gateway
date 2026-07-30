"""Schemas für die Admin-Endpoints (Key-Verwaltung, Usage-Statistik)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class APIKeyCreateRequest(BaseModel):
    user_email: EmailStr = Field(..., description="Wird angelegt, falls noch kein User existiert")
    name: str = Field(..., min_length=1, max_length=100, description="Anzeigename des Keys")
    expires_at: datetime | None = None


class APIKeyCreateResponse(BaseModel):
    id: UUID
    key: str = Field(..., description="Klartext-Key — wird nur genau jetzt einmal angezeigt")
    key_prefix: str


class APIKeyOut(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    user_email: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class UsageByModel(BaseModel):
    provider: str
    model: str
    request_count: int
    total_tokens: int
    total_cost_usd: float


class UsageStatsOut(BaseModel):
    total_requests: int
    total_tokens: int
    total_cost_usd: float
    by_model: list[UsageByModel]
