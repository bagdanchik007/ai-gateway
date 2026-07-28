"""Fehler-Hierarchie für LLM-Provider.

Jeder Provider übersetzt seine nativen SDK-Exceptions in diese Hierarchie.
So kann app/services/llm_router.py providerunabhängig entscheiden, ob ein
Fehler einen Fallback auf den nächsten Provider rechtfertigt (Rate Limit,
Timeout, Unavailable) oder nicht (Auth-Fehler sind Konfigurationsfehler —
ein Fallback mit demselben falschen Key würde genauso scheitern).
"""


class ProviderError(Exception):
    """Basisklasse für alle Provider-Fehler."""


class ProviderAuthenticationError(ProviderError):
    """Ungültiger/fehlender API-Key beim Provider."""


class ProviderRateLimitError(ProviderError):
    """Rate Limit beim Provider erreicht."""


class ProviderTimeoutError(ProviderError):
    """Provider hat nicht rechtzeitig geantwortet."""


class ProviderUnavailableError(ProviderError):
    """Provider ist (temporär) nicht erreichbar, z. B. 5xx-Antwort."""


class ModelNotFoundError(ProviderError):
    """Angefordertes Modell existiert beim Provider nicht."""
