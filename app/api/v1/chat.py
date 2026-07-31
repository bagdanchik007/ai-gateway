"""OpenAI-kompatibler Chat-Completions-Endpoint.

POST /api/v1/chat/completions — erfordert `Authorization: Bearer <api-key>`.
Übersetzt zwischen der öffentlichen (OpenAI-kompatiblen) Wire-Form und dem
internen, provider-agnostischen Schema, ruft den LLMRouter auf und übersetzt
dessen Ergebnis zurück. Streaming folgt in einem späteren Commit.
"""

import json
from collections.abc import AsyncIterator
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_api_key, get_llm_router
from app.db.models.api_key import APIKey
from app.db.session import get_db
from app.providers.exceptions import ProviderError
from app.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionChunkBody,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionMessageParam,
    ChatCompletionRequest,
    ChatCompletionResponseBody,
    ChatCompletionUsage,
    new_completion_id,
)
from app.schemas.llm import ChatCompletionRequest as InternalChatCompletionRequest
from app.schemas.llm import ChatMessage
from app.services.llm_router import LLMRouter
from app.services.memory_service import append_messages, load_history
from app.services.prompt_engine import apply_prompt_engineering, count_tokens
from app.services.usage_tracker import record_usage

router = APIRouter()

logger = structlog.get_logger(__name__)


async def _track_usage_safely(
    db: AsyncSession,
    api_key_id: UUID | None,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """Wrapper um record_usage: ein Tracking-Fehler darf niemals die Chat-Antwort verhindern."""
    try:
        await record_usage(db, api_key_id, provider, model, prompt_tokens, completion_tokens)
    except Exception as exc:  # noqa: BLE001 — bewusst breit, siehe Docstring
        logger.warning("usage.tracking_failed", error=str(exc), provider=provider, model=model)


def _new_messages(body: ChatCompletionRequest) -> list[ChatMessage]:
    """Die vom Client in diesem Request neu mitgeschickten Nachrichten (ohne Historie)."""
    return [ChatMessage(role=m.role, content=m.content) for m in body.messages]


async def _to_internal_request(body: ChatCompletionRequest) -> InternalChatCompletionRequest:
    """Übersetzt die öffentliche Request-Form in unser internes Schema.

    Falls `conversation_id` gesetzt ist, wird die in Redis gespeicherte
    Historie (siehe app/services/memory_service.py) vor die neuen Nachrichten
    gestellt — der Client muss dann nicht bei jedem Request den gesamten
    Verlauf mitschicken.
    """
    new_messages = _new_messages(body)
    history = await load_history(body.conversation_id) if body.conversation_id else []
    return InternalChatCompletionRequest(
        model=body.model,
        messages=[*history, *new_messages],
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )


async def _sse_stream(
    llm_router: LLMRouter,
    internal_request: InternalChatCompletionRequest,
    fallback_models: list[str],
    conversation_id: str | None,
    new_messages: list[ChatMessage],
    db: AsyncSession,
    api_key_id: UUID,
) -> AsyncIterator[str]:
    """Erzeugt Server-Sent Events im OpenAI-Streaming-Format.

    Ein Fehler *während* des Streamens kann dem Client nicht mehr per
    HTTP-Statuscode mitgeteilt werden (Header/200 sind längst gesendet) —
    er wird stattdessen als letztes SSE-Event mit einem "error"-Feld
    ausgeliefert, danach folgt trotzdem das reguläre [DONE].
    """
    completion_id = new_completion_id()
    assistant_content = ""
    seen_provider = "unknown"
    seen_model = internal_request.model
    try:
        async for chunk in llm_router.stream_chat_completion(
            internal_request, fallback_models=fallback_models
        ):
            assistant_content += chunk.delta
            seen_provider = chunk.provider
            seen_model = chunk.model
            body = ChatCompletionChunkBody(
                id=completion_id,
                model=chunk.model,
                choices=[
                    ChatCompletionChunkChoice(
                        delta=ChatCompletionChunkDelta(content=chunk.delta or None),
                        finish_reason=chunk.finish_reason,
                    )
                ],
            )
            yield f"data: {body.model_dump_json()}\n\n"
    except ProviderError as exc:
        error_payload = {"error": {"message": str(exc), "type": exc.__class__.__name__}}
        yield f"data: {json.dumps(error_payload)}\n\n"
        yield "data: [DONE]\n\n"
        return

    yield "data: [DONE]\n\n"

    if conversation_id:
        # Erst NACH erfolgreichem Streamende speichern — bei einem Fehler
        # (siehe except oben, endet dort per `return`) landet keine
        # unvollständige Assistant-Antwort in der Historie.
        await append_messages(
            conversation_id, [*new_messages, ChatMessage(role="assistant", content=assistant_content)]
        )

    # Streaming-Chunks tragen keine exakte Provider-Usage (die meisten Provider
    # liefern die erst mit dem allerletzten Chunk, wenn überhaupt) — daher hier
    # eine Schätzung per Tokenizer statt exakter Zahlen wie im Non-Stream-Pfad.
    prompt_tokens = sum(count_tokens(m.content) for m in internal_request.messages)
    completion_tokens = count_tokens(assistant_content)
    await _track_usage_safely(
        db, api_key_id, seen_provider, seen_model, prompt_tokens, completion_tokens
    )


@router.post(
    "/completions",
    response_model=ChatCompletionResponseBody,
    summary="Chat Completions (OpenAI-kompatibel)",
)
async def create_chat_completion(
    body: ChatCompletionRequest,
    api_key: APIKey = Depends(get_current_api_key),
    llm_router: LLMRouter = Depends(get_llm_router),
    db: AsyncSession = Depends(get_db),
) -> ChatCompletionResponseBody | StreamingResponse:
    new_messages = _new_messages(body)
    internal_request = apply_prompt_engineering(await _to_internal_request(body))

    if body.stream:
        return StreamingResponse(
            _sse_stream(
                llm_router,
                internal_request,
                body.fallback_models,
                body.conversation_id,
                new_messages,
                db,
                api_key.id,
            ),
            media_type="text/event-stream",
        )

    # Kein try/except mehr nötig: ein ProviderError propagiert bis zu den
    # globalen Exception-Handlern (app/core/exception_handlers.py), die ihn
    # in eine konsistente Fehlerantwort übersetzen.
    result = await llm_router.chat_completion(
        internal_request, fallback_models=body.fallback_models
    )

    if body.conversation_id:
        await append_messages(
            body.conversation_id,
            [*new_messages, ChatMessage(role="assistant", content=result.content)],
        )

    await _track_usage_safely(
        db,
        api_key.id,
        result.provider,
        result.model,
        result.usage.prompt_tokens,
        result.usage.completion_tokens,
    )

    return ChatCompletionResponseBody(
        id=new_completion_id(),
        model=result.model,
        choices=[
            ChatCompletionChoice(
                message=ChatCompletionMessageParam(role="assistant", content=result.content),
                finish_reason=result.finish_reason,
            )
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
        ),
    )
