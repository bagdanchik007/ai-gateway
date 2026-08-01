"""Anthropic-Provider (Claude).

Die Anthropic Messages API unterscheidet sich in mehreren Punkten von OpenAI:
1. Der System-Prompt ist ein eigener `system`-Parameter, keine Nachricht mit
   role="system" in der messages-Liste.
2. `max_tokens` ist ein Pflichtfeld, nicht optional wie bei OpenAI.
3. Tool-Aufrufe/-Ergebnisse sind Content-Blocks (`tool_use`/`tool_result`)
   innerhalb einer Message, keine eigene Message-Rolle wie OpenAIs "tool".
4. Tool-Argumente kommen als dict (`input`) zurueck, nicht als JSON-String --
   wir wandeln das fuer unser normalisiertes Schema in einen JSON-String um,
   analog zur OpenAI-Konvention.
Alles wird hier ausgeglichen, damit der Rest des Systems weiterhin nur das
provider-agnostische ChatCompletionRequest-Schema kennt.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam

from app.providers.base import BaseLLMProvider
from app.providers.exceptions import (
    ModelNotFoundError,
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas.llm import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Tool,
    ToolCall,
    ToolCallFunction,
    Usage,
)

_DEFAULT_MAX_TOKENS = 4096


def _to_anthropic_messages(request: ChatCompletionRequest) -> tuple[str | None, list[MessageParam]]:
    """Trennt den System-Prompt heraus und uebersetzt Tool-Calls/-Results in Content-Blocks.

    Mehrere aufeinanderfolgende `tool`-Messages (z. B. Ergebnisse mehrerer
    parallel angeforderter Tool-Calls) werden zu einer einzigen User-Message
    mit mehreren `tool_result`-Blocks zusammengefuehrt -- Anthropic erwartet
    strikt alternierende user/assistant-Rollen.
    """
    system: str | None = None
    messages: list[MessageParam] = []

    for m in request.messages:
        if m.role == "system":
            system = m.content
            continue

        if m.role == "assistant" and m.tool_calls:
            blocks: list[dict[str, Any]] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": json.loads(tc.function.arguments or "{}"),
                    }
                )
            messages.append({"role": "assistant", "content": blocks})  # type: ignore[typeddict-item]
            continue

        if m.role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": m.tool_call_id,
                "content": m.content or "",
            }
            last = messages[-1] if messages else None
            if (
                last is not None
                and last["role"] == "user"
                and isinstance(last["content"], list)
                and all(b.get("type") == "tool_result" for b in last["content"])
            ):
                last["content"].append(block)
            else:
                messages.append({"role": "user", "content": [block]})  # type: ignore[list-item]
            continue

        messages.append({"role": m.role, "content": m.content or ""})

    return system, messages


def _tools_param(tools: list[Tool] | None) -> list[dict[str, Any]] | anthropic.Omit:
    if not tools:
        return anthropic.omit
    return [
        {
            "name": t.function.name,
            "description": t.function.description or "",
            "input_schema": t.function.parameters or {"type": "object", "properties": {}},
        }
        for t in tools
    ]


def _tool_choice_param(tool_choice: str | dict[str, Any] | None) -> dict[str, Any] | anthropic.Omit:
    """Uebersetzt die OpenAI-Konvention (str/dict) in Anthropics {"type": ...}-Form."""
    if tool_choice is None:
        return anthropic.omit
    if tool_choice == "auto":
        return {"type": "auto"}
    if tool_choice == "required":
        return {"type": "any"}
    if tool_choice == "none":
        return anthropic.omit
    if isinstance(tool_choice, dict):
        name = tool_choice.get("function", {}).get("name")
        if name:
            return {"type": "tool", "name": name}
    return anthropic.omit


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, name: str, api_key: str) -> None:
        self.name = name
        self._client = AsyncAnthropic(api_key=api_key)

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        system, messages = _to_anthropic_messages(request)
        try:
            response = await self._client.messages.create(
                model=request.model,
                system=system or anthropic.omit,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens or _DEFAULT_MAX_TOKENS,
                tools=_tools_param(request.tools),  # type: ignore[arg-type]
                tool_choice=_tool_choice_param(request.tool_choice),  # type: ignore[arg-type]
            )
        except Exception as exc:
            raise self._translate_error(exc) from exc

        text = "".join(block.text for block in response.content if block.type == "text")
        tool_calls = [
            ToolCall(
                id=block.id,
                function=ToolCallFunction(name=block.name, arguments=json.dumps(block.input)),
            )
            for block in response.content
            if block.type == "tool_use"
        ] or None

        return ChatCompletionResponse(
            id=response.id,
            model=response.model,
            provider=self.name,
            content=text,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason,
            usage=Usage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
        )

    async def stream_chat_completion(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        # Hinweis: Tool-Call-Deltas werden beim Streaming aktuell nicht
        # inkrementell durchgereicht (Anthropics Event-Stream liefert sie als
        # `input_json_delta`-Fragmente, deren Rekonstruktion hier bewusst noch
        # nicht implementiert ist). Fuer Tool-Calling ohne Streaming siehe
        # `chat_completion` oben -- das ist der in der Praxis uebliche Fall,
        # da nach einem Tool-Call ohnehin auf das Ergebnis gewartet wird.
        system, messages = _to_anthropic_messages(request)
        try:
            async with self._client.messages.stream(
                model=request.model,
                system=system or anthropic.omit,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens or _DEFAULT_MAX_TOKENS,
                tools=_tools_param(request.tools),  # type: ignore[arg-type]
                tool_choice=_tool_choice_param(request.tool_choice),  # type: ignore[arg-type]
            ) as stream:
                async for text in stream.text_stream:
                    yield ChatCompletionChunk(
                        id=request.model,
                        model=request.model,
                        provider=self.name,
                        delta=text,
                        finish_reason=None,
                    )
                final = await stream.get_final_message()
                tool_calls = [
                    ToolCall(
                        id=block.id,
                        function=ToolCallFunction(name=block.name, arguments=json.dumps(block.input)),
                    )
                    for block in final.content
                    if block.type == "tool_use"
                ] or None
                yield ChatCompletionChunk(
                    id=final.id,
                    model=final.model,
                    provider=self.name,
                    delta="",
                    tool_calls=tool_calls,
                    finish_reason=final.stop_reason,
                )
        except Exception as exc:
            raise self._translate_error(exc) from exc

    def _translate_error(self, exc: Exception) -> ProviderError:
        if isinstance(exc, anthropic.AuthenticationError):
            return ProviderAuthenticationError(str(exc))
        if isinstance(exc, anthropic.RateLimitError):
            return ProviderRateLimitError(str(exc))
        if isinstance(exc, anthropic.APITimeoutError):
            return ProviderTimeoutError(str(exc))
        if isinstance(exc, anthropic.NotFoundError):
            return ModelNotFoundError(str(exc))
        return ProviderUnavailableError(str(exc))
