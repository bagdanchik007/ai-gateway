"""Embedding-Erzeugung für RAG.

Nutzt OpenAIs Embedding-API (`text-embedding-3-small`, 1536 Dimensionen).
Ohne konfigurierten `OPENAI_API_KEY` greift ein deterministischer,
netzwerkfreier Fallback — damit lässt sich das RAG-Modul lokal ausprobieren
(z. B. in CI oder Dev-Setups ohne Provider-Keys), allerdings mit spürbar
schlechterer Retrieval-Qualität, da der Fallback kein semantisches
Verständnis hat.
"""

import hashlib

from openai import AsyncOpenAI

from app.core.config import get_settings

_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIM = 1536


async def get_embedding(text: str) -> list[float]:
    settings = get_settings()
    if not settings.openai_api_key:
        return _fallback_embedding(text)

    client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    response = await client.embeddings.create(model=_EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def _fallback_embedding(text: str) -> list[float]:
    """Deterministischer Pseudo-Embedding-Vektor ohne Netzwerkzugriff.

    Kein semantisches Verständnis — rein für lokale Tests/Demo-Zwecke ohne
    OpenAI-Key. Aus einem SHA256-Hash des Texts werden reproduzierbare
    Float-Werte fester Dimension abgeleitet, sodass identischer Text immer
    denselben Vektor ergibt (nötig für konsistente Cosine-Similarity-Werte).
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [(b / 255.0) * 2 - 1 for b in digest]
    repeated = (values * (_EMBEDDING_DIM // len(values) + 1))[:_EMBEDDING_DIM]
    return repeated
