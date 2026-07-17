"""Zentrale Konfiguration der Anwendung.

Einzige Quelle der Wahrheit für alle Einstellungen. Werte werden aus Umgebungs-
variablen (bzw. der .env-Datei — siehe .env.example) gelesen und von pydantic
validiert. Das verhindert über den Code verstreute os.getenv()-Aufrufe mit
versteckten Defaults und Tippfehlern in Variablennamen.

Die Konfiguration sollte über Depends(get_settings) in Routen/Services verwendet
werden, nicht über einen direkten Import des `settings`-Objekts — so lässt sich
die Konfiguration in Tests leicht austauschen (dependency_overrides).
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: Literal["local", "staging", "production"] = "local"
    app_debug: bool = True
    app_port: int = 8000
    secret_key: SecretStr

    # --- Database ---
    database_url: str

    # --- Redis (Rate Limiting, Cache, Usage-Zähler) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- LLM providers ---
    # Die Keys sind auf Konfigurationsebene optional: der jeweilige Provider
    # entscheidet selbst, ob er verfügbar ist (siehe providers/registry in Etappe 2).
    # So lässt sich das Gateway auch mit nur einem konfigurierten Provider starten.
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    xai_api_key: SecretStr | None = None
    local_llm_base_url: str | None = None
    local_llm_api_key: SecretStr | None = None

    # --- Rate limiting ---
    rate_limit_requests_per_minute: int = Field(default=60, gt=0)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Gibt eine gecachte Instanz der Settings zurück.

    lru_cache garantiert, dass die .env nur einmal pro Prozess-Lebensdauer
    geparst wird, statt bei jedem Aufruf. FastAPI-Endpunkte erhalten die
    Settings über Depends(get_settings).
    """
    return Settings()
