"""OpenAI-kompatible Schemas für den öffentlichen Chat-Completions-Endpoint.

Diese Schemas bilden die Wire-Struktur von
https://platform.openai.com/docs/api-reference/chat nach, damit bestehende
OpenAI-SDKs/Clients unser Gateway als Drop-in-Replacement nutzen können
(nur `base_url` ändern). Intern übersetzen wir in/aus den provider-
agnostischen Schemas aus app/schemas/llm.py.
"""

import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ChatCompletionMessageParam(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """Request-Body für POST /api/v1/chat/completions."""

    model: str = Field(..., description="'<provider>:<model>', z. B. 'openai:gpt-4o-mini'")
    messages: list[ChatCompletionMessageParam]
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    stream: bool = False

    # Gateway-Erweiterungen, kein OpenAI-Standard — von echten OpenAI-Clients
    # einfach ignoriert (extra Felder werden von deren SDKs nicht gesendet),
    # nützlich für eigene Clients dieses Gateways.
    fallback_models: list[str] = Field(
        default_factory=list,
        description="Fallback-Kette bei Providerfehlern, z. B. ['anthropic:claude-3-5-haiku-20241022']",
    )
    conversation_id: str | None = Field(
        default=None,
        description="Falls gesetzt: Server-seitige Chat-Historie (siehe memory_service) wird vorangestellt",
    )


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionMessageParam
    finish_reason: str | None = None


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponseBody(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


class ChatCompletionChunkDelta(BaseModel):
    role: Literal["assistant"] | None = None
    content: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: str | None = None


class ChatCompletionChunkBody(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChunkChoice]


def new_completion_id() -> str:
    """Erzeugt eine OpenAI-ähnliche Completion-ID (Präfix 'chatcmpl-')."""
    return f"chatcmpl-{uuid.uuid4().hex}"
