"""Integrationstest für den WebSocket-Chat-Endpoint.

Nutzt dependency_overrides wie tests/integration/test_chat_endpoint.py.
Die Auth läuft hier allerdings über die erste WS-Nachricht statt über
Depends(get_current_api_key) — daher wird get_current_api_key hier NICHT
überschrieben, sondern app.api.v1.chat_ws._authenticate real gegen eine
echte DB-Session getestet (siehe conftest-lose Nutzung von get_db real).
"""

from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock, patch

import pytest
from app.api.deps import get_llm_router
from app.db.models.api_key import APIKey
from app.db.models.user import User
from app.main import app
from app.providers.base import BaseLLMProvider
from app.schemas.llm import ChatCompletionChunk
from app.services.llm_router import LLMRouter
from starlette.testclient import TestClient


class _EchoStreamProvider(BaseLLMProvider):
    name = "fake"

    async def chat_completion(self, request):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def stream_chat_completion(self, request) -> AsyncIterator[ChatCompletionChunk]:  # type: ignore[no-untyped-def]
        for word in ["Hallo", " ", "Welt"]:
            yield ChatCompletionChunk(id="c", model=request.model, provider=self.name, delta=word)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_llm_router] = lambda: LLMRouter({"fake": _EchoStreamProvider()})
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _fake_authenticated_api_key() -> APIKey:
    user = User(email="ws@example.com", is_active=True)
    api_key = APIKey(user_id=None, name="ws", key_hash="x", key_prefix="sk-gw-test")
    api_key.user = user
    return api_key


def test_rejects_first_message_that_is_not_auth(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json({"type": "message", "model": "fake:test", "messages": []})
        with pytest.raises(Exception):  # noqa: B017 — Verbindung wird geschlossen, kein spezifischer Typ nötig
            ws.receive_json()


def test_full_turn_streams_chunks_and_done(client: TestClient) -> None:
    with (
        patch(
            "app.api.v1.chat_ws._authenticate",
            new=AsyncMock(return_value=_fake_authenticated_api_key()),
        ),
        patch("app.api.v1.chat_ws.record_usage", new=AsyncMock()),
        client.websocket_connect("/api/v1/chat/ws") as ws,
    ):
        # Kein "auth"-Send hier: _authenticate ist gemockt und konsumiert daher
        # keine Nachricht selbst — die erste vom Client gesendete Nachricht
        # landet direkt in der message-Loop.
        ws.send_json(
            {"type": "message", "model": "fake:test", "messages": [{"role": "user", "content": "hi"}]}
        )

        deltas = []
        while True:
            msg = ws.receive_json()
            if msg["type"] == "chunk":
                deltas.append(msg["delta"])
            else:
                assert msg["type"] == "done"
                assert msg["usage"]["total_tokens"] > 0
                break

        assert "".join(deltas) == "Hallo Welt"


def test_invalid_message_type_returns_error_without_closing(client: TestClient) -> None:
    with (
        patch(
            "app.api.v1.chat_ws._authenticate",
            new=AsyncMock(return_value=_fake_authenticated_api_key()),
        ),
        client.websocket_connect("/api/v1/chat/ws") as ws,
    ):
        ws.send_json({"type": "unbekannt"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
