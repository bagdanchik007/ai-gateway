"""OpenAI-kompatible Schemas für den öffentlichen Chat-Completions-Endpoint."""

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.llm import Tool, ToolCall


class ChatCompletionMessageParam(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "model": "openai:gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Erkläre mir Kubernetes in 2 Sätzen."}],
                    "fallback_models": ["anthropic:claude-3-5-haiku-20241022"],
                }
            ]
        }
    }

    model: str = Field(..., description="'<provider>:<model>', z. B. 'openai:gpt-4o-mini'")
    messages: list[ChatCompletionMessageParam]
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    stream: bool = False
    fallback_models: list[str] = Field(default_factory=list)
    conversation_id: str | None = Field(default=None)
    tools: list[Tool] | None = Field(
        default=None, description="Function-Definitionen, die das Modell aufrufen kann"
    )
    tool_choice: str | dict[str, Any] | None = Field(default=None)


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
    tool_calls: list[ToolCall] | None = None


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
    return f"chatcmpl-{uuid.uuid4().hex}"
