"""Speichern und Durchsuchen von Dokument-Chunks (Retrieval).

Cosine-Similarity wird bewusst in Python berechnet statt per pgvector-
Extension — die müsste auf dem Postgres-Server erst installiert werden, was
für ein "basic" RAG-Modul eine zusätzliche Infra-Hürde wäre. Für Korpusgrößen
im Bereich einiger Tausend Chunks ist das performant genug; darüber hinaus
wäre eine echte Vektor-DB/pgvector der nächste sinnvolle Ausbauschritt.
"""

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document_chunk import DocumentChunk
from app.services.rag.chunking import chunk_text
from app.services.rag.embeddings import get_embedding


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def add_document(
    db: AsyncSession, text: str, collection: str = "default", source: str | None = None
) -> list[DocumentChunk]:
    """Chunkt `text`, erzeugt pro Chunk ein Embedding und persistiert alles."""
    chunks = chunk_text(text)
    records = []
    for chunk in chunks:
        embedding = await get_embedding(chunk)
        record = DocumentChunk(
            collection=collection, source=source, content=chunk, embedding=embedding
        )
        db.add(record)
        records.append(record)
    await db.commit()
    return records


async def search(
    db: AsyncSession, query: str, collection: str = "default", top_k: int = 3
) -> list[tuple[DocumentChunk, float]]:
    """Gibt die `top_k` ähnlichsten Chunks einer Collection zurück, absteigend sortiert."""
    query_embedding = await get_embedding(query)

    result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.collection == collection)
    )
    candidates = result.scalars().all()

    scored = [(c, _cosine_similarity(query_embedding, c.embedding)) for c in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]
