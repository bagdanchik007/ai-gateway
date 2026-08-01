"""Reichert eine Chat-Anfrage mit relevantem Kontext aus dem RAG-Speicher an.

Wird vom Chat-Endpoint aufgerufen, wenn der Client `rag_collection` gesetzt
hat (siehe app/api/v1/chat.py). Der Router/die Provider bekommen davon
nichts mit — sie sehen nur die fertig angereicherte ChatCompletionRequest.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.llm import ChatCompletionRequest, ChatMessage
from app.services.rag.store import search


async def augment_with_context(
    db: AsyncSession, request: ChatCompletionRequest, collection: str, top_k: int = 3
) -> ChatCompletionRequest:
    user_messages = [m for m in request.messages if m.role == "user"]
    if not user_messages:
        return request

    query = user_messages[-1].content or ""
    if not query:
        return request

    results = await search(db, query, collection=collection, top_k=top_k)
    if not results:
        return request

    context = "\n\n".join(f"[{i + 1}] {chunk.content}" for i, (chunk, _score) in enumerate(results))
    context_message = ChatMessage(
        role="system",
        content=(
            "Nutze folgenden Kontext, um die Frage zu beantworten, falls relevant. "
            "Wenn der Kontext nicht hilft, antworte trotzdem normal.\n\n" + context
        ),
    )

    messages = list(request.messages)
    # Kontext direkt vor die letzte User-Message einfügen statt ganz vorne —
    # das hält ihn im Prompt-Engineering-Trunc (Etappe 3) länger relevant,
    # da dessen Kürzung von den ältesten Nachrichten her verwirft.
    messages.insert(len(messages) - 1, context_message)

    return request.model_copy(update={"messages": messages})
