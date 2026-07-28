"""Anthropic-Provider (Claude).

Die Anthropic Messages API unterscheidet sich in zwei Punkten von OpenAI:
1. Der System-Prompt ist ein eigener `system`-Parameter, keine Nachricht mit
   role="system" in der messages-Liste.
2. `max_tokens` ist ein Pflichtfeld, nicht optional wie bei OpenAI.
Beides wird hier ausgeglichen, damit der Rest des Systems weiterhin nur das
provider-agnostische ChatCompletionRequest-Schema kennt.
"""

from collections.abc import AsyncIterator

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
    Usage,
)

# Anthropic verlangt max_tokens zwingend; unsere Requests haben es oft nicht gesetzt.
_DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, name: str, api_key: str) -> None:
        self.name = name
        self._client = AsyncAnthropic(api_key=api_key)

    @staticmethod
    def _split_system(request: ChatCompletionRequest) -> tuple[str | None, list[MessageParam]]:
        """Trennt eine etwaige system-Message aus der Liste heraus (siehe Modul-Docstring)."""
        system: str | None = None
        messages: list[MessageParam] = []
        for m in request.messages:
            if m.role == "system":
                system = m.content
            else:
                messages.append({"role": m.role, "content": m.content})
        return system, messages

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        system, messages = self._split_system(request)
        try:
            response = await self._client.messages.create(
                model=request.model,
                system=system or anthropic.omit,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens or _DEFAULT_MAX_TOKENS,
            )
        except Exception as exc:
            raise self._translate_error(exc) from exc

        text = "".join(block.text for block in response.content if block.type == "text")
        return ChatCompletionResponse(
            id=response.id,
            model=response.model,
            provider=self.name,
            content=text,
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
        system, messages = self._split_system(request)
        try:
            async with self._client.messages.stream(
                model=request.model,
                system=system or anthropic.omit,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens or _DEFAULT_MAX_TOKENS,
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
                yield ChatCompletionChunk(
                    id=final.id,
                    model=final.model,
                    provider=self.name,
                    delta="",
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
