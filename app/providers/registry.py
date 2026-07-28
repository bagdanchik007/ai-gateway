"""Provider-Registry.

Baut aus den Settings die Menge der tatsächlich konfigurierten Provider auf.
Provider ohne API-Key werden übersprungen statt das Gateway crashen zu
lassen — so läuft der Service auch mit nur einem konfigurierten Provider.
"""

from app.core.config import Settings, get_settings
from app.providers.anthropic import AnthropicProvider
from app.providers.base import BaseLLMProvider
from app.providers.openai import OpenAIProvider


def build_providers(settings: Settings | None = None) -> dict[str, BaseLLMProvider]:
    """Erzeugt alle Provider, für die ein API-Key/Base-URL konfiguriert ist."""
    settings = settings or get_settings()
    providers: dict[str, BaseLLMProvider] = {}

    if settings.openai_api_key:
        providers["openai"] = OpenAIProvider(
            name="openai", api_key=settings.openai_api_key.get_secret_value()
        )

    if settings.anthropic_api_key:
        providers["anthropic"] = AnthropicProvider(
            name="anthropic", api_key=settings.anthropic_api_key.get_secret_value()
        )

    if settings.xai_api_key:
        # xAI (Grok) bietet eine OpenAI-kompatible API — kein eigener Provider-Code nötig.
        providers["grok"] = OpenAIProvider(
            name="grok",
            api_key=settings.xai_api_key.get_secret_value(),
            base_url="https://api.x.ai/v1",
        )

    if settings.local_llm_base_url:
        # Ollama/vLLM/LM Studio & Co. — ebenfalls OpenAI-kompatibel.
        local_key = (
            settings.local_llm_api_key.get_secret_value()
            if settings.local_llm_api_key
            else "not-needed"
        )
        providers["local"] = OpenAIProvider(
            name="local", api_key=local_key, base_url=settings.local_llm_base_url
        )

    return providers
