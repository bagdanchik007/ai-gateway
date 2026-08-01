"""OpenAI-Provider (deckt auch Grok/lokale Modelle über base_url ab)."""

from collections.abc import AsyncIterator
from typing import Any, cast

import openai
from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletionChunk as OpenAIChatCompletionChunk

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
    ChatMessage,
    Tool,
    ToolCall,
    ToolCallFunction,
    Usage,
)


def _to_openai_message(m: ChatMessage) -> dict[str, Any]:
    """Baut das OpenAI-Message-Dict abhängig von der Rolle.

    Kein simples `model_dump()`: OpenAI akzeptiert je Rolle nur bestimmte
    Felder — eine `tool`-Message z. B. nur `tool_call_id` + `content`,
    eine Assistant-Message mit Tool-Calls oft `content=None`.
    """
    if m.role == "tool":
        return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content or ""}

    message: dict[str, Any] = {"role": m.role}
    if m.tool_calls:
        message["tool_calls"] = [tc.model_dump() for tc in m.tool_calls]
        if m.content is not None:
            message["content"] = m.content
    else:
        message["content"] = m.content or ""
    return message


def _tools_param(tools: list[Tool] | None) -> list[dict[str, Any]] | openai.NotGiven:
    if not tools:
        return openai.NOT_GIVEN
    return [t.model_dump() for t in tools]


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, name: str, api_key: str, base_url: str | None = None) -> None:
        self.name = name
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        try:
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=request.model,
                messages=[_to_openai_message(m) for m in request.messages],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                tools=_tools_param(request.tools),
                tool_choice=request.tool_choice if request.tool_choice is not None else openai.NOT_GIVEN,
            )
        except Exception as exc:
            raise self._translate_error(exc) from exc

        choice = response.choices[0]
        usage = response.usage
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    function=ToolCallFunction(name=tc.function.name, arguments=tc.function.arguments),
                )
                for tc in choice.message.tool_calls
            ]

        return ChatCompletionResponse(
            id=response.id,
            model=response.model,
            provider=self.name,
            content=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            usage=Usage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
        )

    async def stream_chat_completion(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        try:
            raw_stream = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=request.model,
                messages=[_to_openai_message(m) for m in request.messages],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                tools=_tools_param(request.tools),
                tool_choice=request.tool_choice if request.tool_choice is not None else openai.NOT_GIVEN,
                stream=True,
            )
            stream = cast(AsyncStream[OpenAIChatCompletionChunk], raw_stream)
            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                delta = choice.delta.content if choice and choice.delta else None

                tool_call_deltas = None
                if choice and choice.delta and choice.delta.tool_calls:
                    # Vereinfachung: OpenAI streamt tool_calls indexbasiert und
                    # sendet id/name nur im ersten Chunk je Call, danach nur
                    # Argument-Fragmente. Wir reichen jedes Fragment einzeln
                    # durch — der Client muss die `arguments`-Strings über die
                    # Chunks hinweg selbst aneinanderhängen (Standardverhalten
                    # bei OpenAI-kompatiblen Streaming-Clients).
                    tool_call_deltas = [
                        ToolCall(
                            id=tc.id or "",
                            function=ToolCallFunction(
                                name=(tc.function.name or "") if tc.function else "",
                                arguments=(tc.function.arguments or "") if tc.function else "",
                            ),
                        )
                        for tc in choice.delta.tool_calls
                    ]

                yield ChatCompletionChunk(
                    id=chunk.id,
                    model=chunk.model,
                    provider=self.name,
                    delta=delta or "",
                    tool_calls=tool_call_deltas,
                    finish_reason=choice.finish_reason if choice else None,
                )
        except Exception as exc:
            raise self._translate_error(exc) from exc

    def _translate_error(self, exc: Exception) -> ProviderError:
        if isinstance(exc, openai.AuthenticationError):
            return ProviderAuthenticationError(str(exc))
        if isinstance(exc, openai.RateLimitError):
            return ProviderRateLimitError(str(exc))
        if isinstance(exc, openai.APITimeoutError):
            return ProviderTimeoutError(str(exc))
        if isinstance(exc, openai.NotFoundError):
            return ModelNotFoundError(str(exc))
        return ProviderUnavailableError(str(exc))

