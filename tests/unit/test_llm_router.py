"""Tests für die Fallback-Logik des LLMRouter.

Nutzt Fake-Provider statt echter Netzwerkaufrufe — die Tests prüfen die
Router-Logik selbst (wann wird gefallbackt, wann nicht), nicht die
Provider-Implementierungen.
"""

from collections.abc import AsyncIterator

import pytest
from app.providers.base import BaseLLMProvider
from app.providers.exceptions import ProviderAuthenticationError, ProviderRateLimitError
from app.schemas.llm import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Usage,
)
from app.services.llm_router import LLMRouter, NoProviderAvailableError


class _FailingProvider(BaseLLMProvider):
    def __init__(self, name: str, error: Exception) -> None:
        self.name = name
        self.error = error
        self.calls = 0

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        self.calls += 1
        raise self.error

    async def stream_chat_completion(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        raise self.error
        yield  # pragma: no cover


class _WorkingProvider(BaseLLMProvider):
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        self.calls += 1
        return ChatCompletionResponse(
            id="1",
            model=request.model,
            provider=self.name,
            content="hallo",
            usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    async def stream_chat_completion(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        yield ChatCompletionChunk(id="1", model=request.model, provider=self.name, delta="hi")


def _request(model: str) -> ChatCompletionRequest:
    return ChatCompletionRequest(model=model, messages=[ChatMessage(role="user", content="hi")])


async def test_fallback_on_rate_limit() -> None:
    router = LLMRouter(
        {
            "primary": _FailingProvider("primary", ProviderRateLimitError("limit")),
            "backup": _WorkingProvider("backup"),
        }
    )
    result = await router.chat_completion(_request("primary:x"), fallback_models=["backup:y"])
    assert result.provider == "backup"


async def test_no_fallback_on_authentication_error() -> None:
    router = LLMRouter(
        {
            "primary": _FailingProvider("primary", ProviderAuthenticationError("bad key")),
            "backup": _WorkingProvider("backup"),
        }
    )
    with pytest.raises(ProviderAuthenticationError):
        await router.chat_completion(_request("primary:x"), fallback_models=["backup:y"])


async def test_no_provider_available_when_all_fail() -> None:
    router = LLMRouter({"primary": _FailingProvider("primary", ProviderRateLimitError("limit"))})
    with pytest.raises(NoProviderAvailableError):
        await router.chat_completion(_request("primary:x"), fallback_models=[])


async def test_unconfigured_provider_is_skipped() -> None:
    router = LLMRouter({"backup": _WorkingProvider("backup")})
    result = await router.chat_completion(_request("missing:x"), fallback_models=["backup:y"])
    assert result.provider == "backup"


async def test_streaming_fallback_before_first_chunk() -> None:
    router = LLMRouter(
        {
            "primary": _FailingProvider("primary", ProviderRateLimitError("limit")),
            "backup": _WorkingProvider("backup"),
        }
    )
    chunks = [
        chunk
        async for chunk in router.stream_chat_completion(
            _request("primary:x"), fallback_models=["backup:y"]
        )
    ]
    assert len(chunks) == 1
    assert chunks[0].provider == "backup"


async def test_streaming_no_fallback_after_first_chunk() -> None:
    class _FailsAfterOneChunk(BaseLLMProvider):
        name = "flaky"

        async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
            raise NotImplementedError

        async def stream_chat_completion(
            self, request: ChatCompletionRequest
        ) -> AsyncIterator[ChatCompletionChunk]:
            yield ChatCompletionChunk(id="1", model=request.model, provider=self.name, delta="a")
            raise ProviderRateLimitError("mid-stream failure")

    router = LLMRouter({"flaky": _FailsAfterOneChunk(), "backup": _WorkingProvider("backup")})
    with pytest.raises(ProviderRateLimitError):
        _ = [
            chunk
            async for chunk in router.stream_chat_completion(
                _request("flaky:x"), fallback_models=["backup:y"]
            )
        ]
