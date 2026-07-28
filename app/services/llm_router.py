"""LLM-Router mit Fallback-Logik.

Modelle werden als "<provider>:<model>" adressiert, z. B. "openai:gpt-4o-mini".
Zu jedem Request kann eine Fallback-Kette übergeben werden: schlägt der
primäre Provider mit einem fallback-würdigen Fehler fehl (Rate Limit,
Timeout, Unavailable — nicht bei Auth-Fehlern, das sind Konfigurationsfehler,
die beim nächsten Versuch mit demselben Key genauso scheitern würden), wird
automatisch der nächste Provider in der Kette versucht.
"""

import structlog

from app.providers.base import BaseLLMProvider
from app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas.llm import ChatCompletionRequest, ChatCompletionResponse

logger = structlog.get_logger(__name__)

# Fehlertypen, bei denen ein Fallback auf den nächsten Provider sinnvoll ist.
_FALLBACK_WORTHY = (ProviderRateLimitError, ProviderTimeoutError, ProviderUnavailableError)


class NoProviderAvailableError(ProviderError):
    """Alle Provider in der Fallback-Kette sind fehlgeschlagen oder nicht konfiguriert."""


class ModelReference:
    """Zerlegt eine 'provider:model'-Modell-ID in ihre Bestandteile."""

    __slots__ = ("provider", "model")

    def __init__(self, raw: str) -> None:
        provider, _, model = raw.partition(":")
        if not model:
            raise ValueError(f"Modell-ID muss die Form 'provider:model' haben, bekommen: {raw!r}")
        self.provider = provider
        self.model = model


class LLMRouter:
    def __init__(self, providers: dict[str, BaseLLMProvider]) -> None:
        self._providers = providers

    async def chat_completion(
        self, request: ChatCompletionRequest, fallback_models: list[str] | None = None
    ) -> ChatCompletionResponse:
        """Versucht `request.model`, bei fallback-würdigem Fehler dann `fallback_models` der Reihe nach."""
        chain = [request.model, *(fallback_models or [])]
        last_error: Exception | None = None

        for model_id in chain:
            ref = ModelReference(model_id)
            provider = self._providers.get(ref.provider)
            if provider is None:
                logger.warning("llm_router.provider_not_configured", provider=ref.provider)
                continue

            sub_request = request.model_copy(update={"model": ref.model})
            try:
                return await provider.chat_completion(sub_request)
            except ProviderAuthenticationError:
                # Kein Fallback bei Auth-Fehlern: das ist ein Konfigurationsfehler,
                # kein transientes Problem — der Aufrufer soll ihn sofort sehen.
                raise
            except _FALLBACK_WORTHY as exc:
                logger.warning(
                    "llm_router.fallback",
                    failed_provider=ref.provider,
                    failed_model=ref.model,
                    error=str(exc),
                )
                last_error = exc
                continue

        raise NoProviderAvailableError(
            f"Alle Provider in der Kette sind fehlgeschlagen oder nicht konfiguriert: {chain}"
        ) from last_error
