"""Normalisierte Schemas für die Kommunikation mit LLM-Providern.

Diese Schemas sind provider-agnostisch: jeder Provider übersetzt sein
natives Request-/Response-Format in diese Form und zurück. Der Rest des
Systems (Router, Chat-API in Etappe 3) kennt nur diese Schemas, nie die
provider-spezifischen SDK-Typen von OpenAI/Anthropic/etc.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(
        ..., description="Modell-ID, z. B. 'gpt-4o-mini' oder 'claude-3-5-sonnet-20241022'"
    )
    messages: list[ChatMessage]
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    model: str
    provider: str
    content: str
    finish_reason: str | None = None
    usage: Usage


class ChatCompletionChunk(BaseModel):
    id: str
    model: str
    provider: str
    delta: str
    finish_reason: str | None = None
