"""Tests für app/services/cost_calculator.py."""

from app.services.cost_calculator import calculate_cost_usd


def test_known_model_cost_matches_pricing_table() -> None:
    # gpt-4o-mini: 0.15 USD/1M input, 0.60 USD/1M output
    cost = calculate_cost_usd("openai", "gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
    expected = (100 / 1_000_000) * 0.15 + (50 / 1_000_000) * 0.60
    assert cost == round(expected, 6)


def test_unknown_model_costs_zero_instead_of_raising() -> None:
    cost = calculate_cost_usd("unknown-provider", "unknown-model", 1000, 1000)
    assert cost == 0.0


def test_zero_tokens_cost_zero() -> None:
    cost = calculate_cost_usd("openai", "gpt-4o-mini", 0, 0)
    assert cost == 0.0
