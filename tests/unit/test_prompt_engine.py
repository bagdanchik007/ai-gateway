"""Tests für den Prompt-Engineering-Service."""

from app.schemas.llm import ChatCompletionRequest, ChatMessage
from app.services.prompt_engine import apply_prompt_engineering


def test_inserts_default_system_prompt_when_missing() -> None:
    request = ChatCompletionRequest(
        model="x:y", messages=[ChatMessage(role="user", content="hi")]
    )
    result = apply_prompt_engineering(request)
    assert result.messages[0].role == "system"


def test_keeps_existing_system_prompt_unchanged() -> None:
    request = ChatCompletionRequest(
        model="x:y",
        messages=[
            ChatMessage(role="system", content="Custom prompt"),
            ChatMessage(role="user", content="hi"),
        ],
    )
    result = apply_prompt_engineering(request)
    system_messages = [m for m in result.messages if m.role == "system"]
    assert len(system_messages) == 1
    assert system_messages[0].content == "Custom prompt"


def test_truncates_history_to_token_budget() -> None:
    long_text = "Wort " * 200
    messages = [
        ChatMessage(role="user" if i % 2 == 0 else "assistant", content=long_text)
        for i in range(20)
    ]
    request = ChatCompletionRequest(model="x:y", messages=messages)
    result = apply_prompt_engineering(request, token_budget=500)

    assert len(result.messages) < len(messages) + 1  # +1 für den eingefügten System-Prompt
    # Die juengste Nachricht muss immer erhalten bleiben.
    assert result.messages[-1].content == messages[-1].content


def test_truncation_keeps_at_least_one_message() -> None:
    """Selbst bei einem winzigen Budget darf nie die komplette Historie verworfen werden."""
    messages = [ChatMessage(role="user", content="Wort " * 500)]
    request = ChatCompletionRequest(model="x:y", messages=messages)
    result = apply_prompt_engineering(request, token_budget=1)

    non_system = [m for m in result.messages if m.role != "system"]
    assert len(non_system) == 1
