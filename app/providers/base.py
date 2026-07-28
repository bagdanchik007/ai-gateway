"""Basis-Interface für alle LLM-Provider.

Ein neuer Provider = eine neue Klasse, die dieses Interface implementiert.
Weder app/api/ noch app/services/llm_router.py müssen dafür geändert werden —
nur app/providers/registry.py muss den neuen Provider registrieren.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.schemas.llm import ChatCompletionChunk, ChatCompletionRequest, ChatCompletionResponse


class BaseLLMProvider(ABC):
    """Abstraktes Interface für einen LLM-Provider."""

    name: str  # z. B. "openai", "anthropic" — für Logging, Usage-Tracking, Fehlermeldungen

    @abstractmethod
    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Führt eine nicht-gestreamte Chat-Completion aus."""
        raise NotImplementedError

    @abstractmethod
    def stream_chat_completion(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Führt eine gestreamte Chat-Completion aus."""
        raise NotImplementedError
