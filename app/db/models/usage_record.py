"""UsageRecord-Modell.

Ein Datensatz pro abgeschlossener Chat-Completion (siehe Etappe 3). Grundlage
für Kosten-Reporting und spätere Kontingente/Abrechnung pro User.

Bewusst denormalisiert: `provider`/`model` sind Strings, keine Foreign Keys.
Provider und Modelle ändern sich häufiger als das Schema, und historische
Einträge sollen auch nach Entfernen eines Providers/Modells lesbar bleiben.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # ondelete="SET NULL": ein gelöschter API-Key soll die historischen
    # Usage-Daten nicht mitreißen — Nachvollziehbarkeit für Abrechnung/Audits
    # bleibt erhalten, auch wenn der Key selbst längst widerrufen wurde.
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<UsageRecord id={self.id} provider={self.provider} model={self.model}>"
