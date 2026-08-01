"""Normalisierte Schemas für die Kommunikation mit LLM-Providern."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolFunction(BaseModel):
    """JSON-Schema-Definition einer aufrufbaren Funktion (OpenAI-Konvention)."""

    name: str
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class Tool(BaseModel):
    type: Literal["function"] = "function"
    function: ToolFunction


class ToolCallFunction(BaseModel):
    name: str
    # Bewusst ein JSON-String, nicht dict — entspricht der OpenAI-Konvention
    # und lässt sich verlustfrei über beide Provider-Formate transportieren
    # (Anthropic liefert ein dict zurück, das hier per json.dumps() reinkommt).
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    # Optional, weil eine Assistant-Message bei einem reinen Tool-Call oft
    # keinen Textinhalt hat (nur tool_calls).
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    # Nur bei role="tool": referenziert, welcher ToolCall hiermit beantwortet wird.
    tool_call_id: str | None = None
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="Modell-ID")
    messages: list[ChatMessage]
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    tools: list[Tool] | None = None
    # "auto" | "none" | "required" | {"type": "function", "function": {"name": ...}}
    tool_choice: str | dict[str, Any] | None = None


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    model: str
    provider: str
    content: str
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
    usage: Usage


class ChatCompletionChunk(BaseModel):
    id: str
    model: str
    provider: str
    delta: str
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
