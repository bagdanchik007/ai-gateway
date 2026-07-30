"""Kostenberechnung für LLM-Aufrufe.

Preise sind statisch im Code hinterlegt (USD pro 1 Million Tokens, analog zu
den öffentlichen Preisseiten der Provider). Bewusst einfach gehalten: Preise
ändern sich selten genug, dass ein Redeploy bei einer Preisänderung
akzeptabel ist — ein Datenbank-/Remote-Preiskatalog wäre für diesen Umfang
über-engineered. Unbekannte Modelle liefern Kosten 0.0 statt eines Fehlers,
damit Usage-Tracking nie eine Chat-Anfrage zum Scheitern bringt.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float
    output_per_million: float


# Stand: öffentliche Preislisten der Provider zum Entwicklungszeitpunkt.
# Bei Preisänderungen hier aktualisieren (kein Auto-Sync von den Provider-APIs).
_PRICING: dict[str, ModelPricing] = {
    "openai:gpt-4o": ModelPricing(input_per_million=2.50, output_per_million=10.00),
    "openai:gpt-4o-mini": ModelPricing(input_per_million=0.15, output_per_million=0.60),
    "anthropic:claude-3-5-sonnet-20241022": ModelPricing(
        input_per_million=3.00, output_per_million=15.00
    ),
    "anthropic:claude-3-5-haiku-20241022": ModelPricing(
        input_per_million=0.80, output_per_million=4.00
    ),
}
_UNKNOWN_MODEL_PRICING = ModelPricing(input_per_million=0.0, output_per_million=0.0)


def calculate_cost_usd(
    provider: str, model: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """Berechnet die Kosten eines Requests in USD. 0.0 für unbekannte Modelle."""
    pricing = _PRICING.get(f"{provider}:{model}", _UNKNOWN_MODEL_PRICING)
    input_cost = (prompt_tokens / 1_000_000) * pricing.input_per_million
    output_cost = (completion_tokens / 1_000_000) * pricing.output_per_million
    return round(input_cost + output_cost, 6)
