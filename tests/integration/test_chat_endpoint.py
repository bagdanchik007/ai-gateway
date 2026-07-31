"""Integrationstest für den Chat-Completions-Endpoint.

Nutzt FastAPIs dependency_overrides statt echter Provider/DB — prüft die
Verdrahtung (Auth, Router, Error-Handling), nicht die Provider selbst
(dafür siehe tests/unit/test_llm_router.py) oder eine echte DB (dafür
braucht es Postgres/Redis, siehe README für lokales Setup).
"""

from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock

import pytest
from app.api.deps import get_current_api_key, get_llm_router
from app.db.models.api_key import APIKey
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.providers.base import BaseLLMProvider
from app.schemas.llm import ChatCompletionChunk, ChatCompletionResponse, Usage
from app.services.llm_router import LLMRouter
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient


class _EchoProvider(BaseLLMProvider):
    name = "fake"

    async def chat_completion(self, request):  # type: ignore[no-untyped-def]
        return ChatCompletionResponse(
            id="1",
            model=request.model,
            provider=self.name,
            content=f"Echo: {request.messages[-1].content}",
            finish_reason="stop",
            usage=Usage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        )

    async def stream_chat_completion(self, request) -> AsyncIterator[ChatCompletionChunk]:  # type: ignore[no-untyped-def]
        for word in ["Hallo", " ", "Welt"]:
            yield ChatCompletionChunk(id="c", model=request.model, provider=self.name, delta=word)


@pytest.fixture
def client() -> Iterator[TestClient]:
    fake_user = User(email="test@example.com", is_active=True)
    fake_api_key = APIKey(user_id=None, name="test", key_hash="x", key_prefix="sk-gw-test")
    fake_api_key.user = fake_user

    app.dependency_overrides[get_current_api_key] = lambda: fake_api_key
    app.dependency_overrides[get_llm_router] = lambda: LLMRouter({"fake": _EchoProvider()})
    app.dependency_overrides[get_db] = lambda: AsyncMock(spec=AsyncSession)

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_chat_completion_returns_provider_response(client: TestClient) -> None:
    response = client.post(
        "/api/v1/chat/completions",
        json={"model": "fake:test", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["choices"][0]["message"]["content"] == "Echo: hi"
    assert body["usage"]["total_tokens"] == 10


def test_unconfigured_provider_returns_503_with_consistent_error_shape(client: TestClient) -> None:
    response = client.post(
        "/api/v1/chat/completions",
        json={"model": "unbekannt:x", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["type"] == "no_provider_available"


def test_missing_model_field_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]}
    )
    assert response.status_code == 422
    assert response.json()["error"]["type"] == "validation_error"


def test_streaming_returns_sse_chunks_and_done(client: TestClient) -> None:
    with client.stream(
        "POST",
        "/api/v1/chat/completions",
        json={
            "model": "fake:test",
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    ) as response:
        assert response.status_code == 200
        lines = [line for line in response.iter_lines() if line.startswith("data: ")]

    assert lines[-1] == "data: [DONE]"
    assert len(lines) > 1


def test_health_check_needs_no_auth() -> None:
    with TestClient(app) as c:
        response = c.get("/health")
    assert response.status_code == 200
