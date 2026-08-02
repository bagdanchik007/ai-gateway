"""WebSocket-Variante des Chat-Endpoints.

Bietet dieselbe Chat-Funktionalität wie POST /api/v1/chat/completions, aber
über eine persistente Verbindung statt einzelner HTTP-Requests — sinnvoll
für Clients, die mehrere Turns in einer Session ohne wiederholten
Verbindungsaufbau/Auth-Overhead durchführen (z. B. Browser-Chat-UIs).

Auth läuft bewusst NICHT über einen Query-Parameter (würde in Server-Logs,
Browser-Historie und Referrer-Headern landen), sondern über eine erste
Auth-Nachricht direkt nach dem Verbindungsaufbau:

    Client -> {"type": "auth", "api_key": "sk-gw-..."}
    Server -> {"type": "auth_ok"}  |  Verbindung schließt mit Code 4401

Danach beliebig viele Chat-Turns:

    Client -> {"type": "message", "model": "...", "messages": [...], ...}
    Server -> {"type": "chunk", "delta": "..."}   (mehrfach)
    Server -> {"type": "done", "usage": {...}}
    Server -> {"type": "error", "message": "..."} (statt "done", bei Fehlern)

Das Request-Schema pro "message" ist identisch zu ChatCompletionRequest aus
app/schemas/chat.py (inkl. tools/tool_choice/rag_collection/conversation_id)
— nur `stream` ist irrelevant, da eine WebSocket-Verbindung ohnehin push-basiert ist.
"""

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_llm_router
from app.core.security import hash_api_key
from app.db.models.api_key import APIKey
from app.db.session import get_db
from app.providers.exceptions import ProviderError
from app.schemas.chat import ChatCompletionRequest
from app.schemas.llm import ChatCompletionRequest as InternalChatCompletionRequest
from app.schemas.llm import ChatMessage
from app.services.llm_router import LLMRouter
from app.services.memory_service import append_messages, load_history
from app.services.prompt_engine import apply_prompt_engineering, count_tokens
from app.services.rag.retrieval import augment_with_context
from app.services.usage_tracker import record_usage

logger = structlog.get_logger(__name__)

router = APIRouter()

# 4000-4999 sind laut WebSocket-Spec für Anwendungen reserviert.
_CLOSE_AUTH_FAILED = 4401


async def _authenticate(websocket: WebSocket, db: AsyncSession) -> APIKey | None:
    """Erwartet als erste Nachricht {"type": "auth", "api_key": "..."}."""
    try:
        raw = await websocket.receive_json()
    except (ValueError, WebSocketDisconnect):
        return None

    if not isinstance(raw, dict) or raw.get("type") != "auth" or not raw.get("api_key"):
        await websocket.close(
            code=_CLOSE_AUTH_FAILED,
            reason="Erste Nachricht muss {'type': 'auth', 'api_key': '...'} sein",
        )
        return None

    key_hash = hash_api_key(raw["api_key"])
    result = await db.execute(
        select(APIKey).options(selectinload(APIKey.user)).where(APIKey.key_hash == key_hash)
    )
    api_key = result.scalar_one_or_none()

    if api_key is None or not api_key.is_active or not api_key.user.is_active:
        await websocket.close(code=_CLOSE_AUTH_FAILED, reason="Ungültiger API-Key")
        return None

    await websocket.send_json({"type": "auth_ok"})
    return api_key


def _to_chat_messages(body: ChatCompletionRequest) -> list[ChatMessage]:
    return [
        ChatMessage(
            role=m.role, content=m.content, tool_calls=m.tool_calls, tool_call_id=m.tool_call_id, name=m.name
        )
        for m in body.messages
    ]


async def _handle_turn(
    websocket: WebSocket,
    db: AsyncSession,
    llm_router: LLMRouter,
    api_key: APIKey,
    body: ChatCompletionRequest,
) -> None:
    new_messages = _to_chat_messages(body)
    history = await load_history(body.conversation_id) if body.conversation_id else []
    internal_request = InternalChatCompletionRequest(
        model=body.model,
        messages=[*history, *new_messages],
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        tools=body.tools,
        tool_choice=body.tool_choice,
    )
    if body.rag_collection:
        internal_request = await augment_with_context(
            db, internal_request, collection=body.rag_collection
        )
    internal_request = apply_prompt_engineering(internal_request)

    assistant_content = ""
    seen_provider = "unknown"
    seen_model = internal_request.model
    try:
        async for chunk in llm_router.stream_chat_completion(
            internal_request, fallback_models=body.fallback_models
        ):
            assistant_content += chunk.delta
            seen_provider = chunk.provider
            seen_model = chunk.model
            await websocket.send_json(
                {
                    "type": "chunk",
                    "delta": chunk.delta,
                    "tool_calls": [tc.model_dump() for tc in chunk.tool_calls]
                    if chunk.tool_calls
                    else None,
                    "finish_reason": chunk.finish_reason,
                }
            )
    except ProviderError as exc:
        await websocket.send_json(
            {"type": "error", "message": str(exc), "error_type": exc.__class__.__name__}
        )
        return

    if body.conversation_id:
        await append_messages(
            body.conversation_id,
            [*new_messages, ChatMessage(role="assistant", content=assistant_content)],
        )

    prompt_tokens = sum(count_tokens(m.content or "") for m in internal_request.messages)
    completion_tokens = count_tokens(assistant_content)
    try:
        await record_usage(db, api_key.id, seen_provider, seen_model, prompt_tokens, completion_tokens)
    except Exception as exc:  # noqa: BLE001 — Tracking-Fehler darf den Turn nicht abbrechen
        logger.warning("chat_websocket.usage_tracking_failed", error=str(exc))

    await websocket.send_json(
        {
            "type": "done",
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
    )


@router.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> None:
    await websocket.accept()

    api_key = await _authenticate(websocket, db)
    if api_key is None:
        return

    try:
        while True:
            raw = await websocket.receive_json()
            if not isinstance(raw, dict) or raw.get("type") != "message":
                await websocket.send_json(
                    {"type": "error", "message": "Erwartet: {'type': 'message', ...}"}
                )
                continue

            try:
                body = ChatCompletionRequest.model_validate(
                    {k: v for k, v in raw.items() if k != "type"}
                )
            except ValidationError as exc:
                await websocket.send_json({"type": "error", "message": str(exc.errors())})
                continue

            await _handle_turn(websocket, db, llm_router, api_key, body)
    except WebSocketDisconnect:
        logger.info("chat_websocket.disconnected", api_key_id=str(api_key.id))
