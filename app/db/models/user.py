"""User-Modell.

Ein User kann beliebig viele API-Keys besitzen (z. B. für unterschiedliche
Apps/Umgebungen). Die Authentifizierung am Gateway läuft ausschließlich über
API-Keys, nicht über Passwort-Login — der User dient hier primär als
Besitzer- und Abrechnungseinheit für Usage-Tracking.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.api_key import APIKey


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Steuert Zugriff auf /api/v1/admin/* (siehe app/api/deps.py:get_current_admin_user).
    # Bewusst ein einfaches Bool statt eines Rollen-Systems — reicht für den
    # aktuellen Bedarf (Betreiber vs. normaler API-Nutzer), ein echtes
    # Rollen-/Permission-Modell wäre für diesen Umfang über-engineered.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    api_keys: Mapped[list["APIKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",  # API-Keys werden fast immer zusammen mit dem User gebraucht
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
