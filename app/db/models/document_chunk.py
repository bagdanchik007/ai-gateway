"""DocumentChunk-Modell für RAG.

Ein Chunk = ein Textausschnitt + sein Embedding-Vektor. `collection` erlaubt
mehrere unabhängige Wissensbestände im selben Gateway (z. B. pro Kunde/
Projekt), ohne dass sich Retrieval-Anfragen gegenseitig kontaminieren.
"""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, default="default"
    )
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Natives Postgres-ARRAY statt pgvector-Extension: braucht keine
    # zusätzliche Extension-Installation auf dem DB-Server. Cosine-Similarity
    # wird dafür in Python berechnet (siehe services/rag/store.py) statt per
    # Index-beschleunigter Vektorsuche — für ein "basic" RAG-Modul bewusst
    # in Kauf genommen, siehe Docstring dort.
    embedding: Mapped[list[float]] = mapped_column(ARRAY(Float), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} collection={self.collection!r}>"
