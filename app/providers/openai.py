"""OpenAI-Provider.

Nutzt den offiziellen `openai`-SDK-Client. Da xAI (Grok) und viele lokale
Inference-Server (Ollama, vLLM, LM Studio) OpenAI-kompatible APIs anbieten,
deckt diese eine Klasse über unterschiedliche `base_url`/`api_key`-Werte
(siehe app/providers/registry.py) mehrere Provider ab, ohne Code-Duplizierung.
"""

from collections.abc import AsyncIterator
from typing import cast

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
    Usage,
)


class OpenAIProvider(BaseLLMProvider):
    """Provider für OpenAI und alle OpenAI-kompatiblen APIs (Grok, lokale Modelle)."""

    def __init__(self, name: str, api_key: str, base_url: str | None = None) -> None:
        self.name = name
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        try:
            response = await self._client.chat.completions.create(
                model=request.model,
                messages=[m.model_dump() for m in request.messages],  # type: ignore[misc]
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except Exception as exc:
            raise self._translate_error(exc) from exc

        choice = response.choices[0]
        usage = response.usage
        return ChatCompletionResponse(
            id=response.id,
            model=response.model,
            provider=self.name,
            content=choice.message.content or "",
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
            raw_stream = await self._client.chat.completions.create(
                model=request.model,
                messages=[m.model_dump() for m in request.messages],  # type: ignore[misc]
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True,
            )
            # mypy kann den Overload wegen der zusätzlichen kwargs nicht auf den
            # stream=True-Fall verengen; zur Laufzeit ist der Typ garantiert korrekt.
            stream = cast(AsyncStream[OpenAIChatCompletionChunk], raw_stream)
            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                delta = choice.delta.content if choice and choice.delta else None
                yield ChatCompletionChunk(
                    id=chunk.id,
                    model=chunk.model,
                    provider=self.name,
                    delta=delta or "",
                    finish_reason=choice.finish_reason if choice else None,
                )
        except Exception as exc:
            raise self._translate_error(exc) from exc

    def _translate_error(self, exc: Exception) -> ProviderError:
        """Übersetzt SDK-Exceptions in unsere providerunabhängige Fehler-Hierarchie."""
        if isinstance(exc, openai.AuthenticationError):
            return ProviderAuthenticationError(str(exc))
        if isinstance(exc, openai.RateLimitError):
            return ProviderRateLimitError(str(exc))
        if isinstance(exc, openai.APITimeoutError):
            return ProviderTimeoutError(str(exc))
        if isinstance(exc, openai.NotFoundError):
            return ModelNotFoundError(str(exc))
        return ProviderUnavailableError(str(exc))
