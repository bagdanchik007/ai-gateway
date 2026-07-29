"""Chat-Memory-Service.

Speichert Konversationsverläufe serverseitig in Redis, adressiert über eine
vom Client vergebene `conversation_id`. Clients, die nicht bei jedem Request
die volle Historie mitschicken wollen, referenzieren stattdessen nur die
`conversation_id` — der Chat-Endpoint reichert die Anfrage dann mit der
gespeicherten Historie an (siehe app/api/v1/chat.py).
"""

import json

from app.core.redis import get_redis
from app.schemas.llm import ChatMessage

_KEY_PREFIX = "chat_memory"
_DEFAULT_TTL_SECONDS = 60 * 60 * 24  # 24h — inaktive Konversationen verfallen automatisch
_MAX_MESSAGES = 50  # harte Obergrenze pro Konversation, unabhängig vom Prompt-Engineering-Token-Budget


def _key(conversation_id: str) -> str:
    return f"{_KEY_PREFIX}:{conversation_id}"


async def load_history(conversation_id: str) -> list[ChatMessage]:
    """Lädt die gespeicherte Historie. Leere Liste, falls die Konversation unbekannt/abgelaufen ist."""
    redis = get_redis()
    raw = await redis.get(_key(conversation_id))
    if raw is None:
        return []
    return [ChatMessage.model_validate(item) for item in json.loads(raw)]


async def append_messages(conversation_id: str, messages: list[ChatMessage]) -> None:
    """Hängt neue Nachrichten an, kürzt auf _MAX_MESSAGES und setzt die TTL neu."""
    redis = get_redis()
    history = await load_history(conversation_id)
    history.extend(messages)
    history = history[-_MAX_MESSAGES:]
    payload = json.dumps([m.model_dump() for m in history])
    await redis.set(_key(conversation_id), payload, ex=_DEFAULT_TTL_SECONDS)


async def clear_history(conversation_id: str) -> None:
    redis = get_redis()
    await redis.delete(_key(conversation_id))
