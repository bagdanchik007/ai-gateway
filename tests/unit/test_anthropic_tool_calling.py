"""Tests für die Anthropic-spezifische Übersetzung von Tool-Calls/-Results.

Reine Unit-Tests der Konvertierungsfunktionen — kein Netzwerkzugriff nötig.
Der reale API-Roundtrip ist manuell gegen api.anthropic.com verifiziert
(siehe PR-Beschreibung/Commit-Notizen), aber nicht Teil der automatisierten
Suite, um CI nicht von einem echten API-Key abhängig zu machen.

mypy kennt die exakten Anthropic-SDK-TypedDicts für `messages`/`content`
nicht in dieser generischen Form — für die Tests casten wir das Ergebnis
daher bewusst auf `Any`, statt jede Indexierung einzeln zu ignorieren.
"""

from typing import Any, cast

from app.providers.anthropic import _to_anthropic_messages, _tool_choice_param, _tools_param
from app.schemas.llm import (
    ChatCompletionRequest,
    ChatMessage,
    Tool,
    ToolCall,
    ToolCallFunction,
    ToolFunction,
)


def test_system_prompt_is_split_out() -> None:
    request = ChatCompletionRequest(
        model="x",
        messages=[
            ChatMessage(role="system", content="Sei hilfreich"),
            ChatMessage(role="user", content="Hallo"),
        ],
    )
    system, messages = _to_anthropic_messages(request)
    assert system == "Sei hilfreich"
    assert messages == [{"role": "user", "content": "Hallo"}]


def test_assistant_tool_call_becomes_tool_use_block() -> None:
    request = ChatCompletionRequest(
        model="x",
        messages=[
            ChatMessage(role="user", content="Wetter in Berlin?"),
            ChatMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        function=ToolCallFunction(name="get_weather", arguments='{"city": "Berlin"}'),
                    )
                ],
            ),
        ],
    )
    _, raw_messages = _to_anthropic_messages(request)
    messages = cast(list[dict[str, Any]], raw_messages)

    assistant_message = messages[1]
    assert assistant_message["role"] == "assistant"
    block = assistant_message["content"][0]
    assert block["type"] == "tool_use"
    assert block["id"] == "call_1"
    assert block["input"] == {"city": "Berlin"}


def test_tool_result_becomes_user_message_with_tool_result_block() -> None:
    request = ChatCompletionRequest(
        model="x",
        messages=[ChatMessage(role="tool", tool_call_id="call_1", content="18 Grad, sonnig")],
    )
    _, raw_messages = _to_anthropic_messages(request)
    messages = cast(list[dict[str, Any]], raw_messages)

    assert messages[0]["role"] == "user"
    assert messages[0]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "call_1",
        "content": "18 Grad, sonnig",
    }


def test_consecutive_tool_results_are_merged_into_one_message() -> None:
    """Anthropic erwartet strikt alternierende user/assistant-Rollen —

    mehrere Tool-Results in Folge müssen als EINE User-Message mit mehreren
    tool_result-Blocks gesendet werden, nicht als mehrere User-Messages.
    """
    request = ChatCompletionRequest(
        model="x",
        messages=[
            ChatMessage(role="tool", tool_call_id="call_1", content="A"),
            ChatMessage(role="tool", tool_call_id="call_2", content="B"),
        ],
    )
    _, raw_messages = _to_anthropic_messages(request)
    messages = cast(list[dict[str, Any]], raw_messages)

    assert len(messages) == 1
    assert len(messages[0]["content"]) == 2


def test_tools_param_converts_to_anthropic_input_schema_shape() -> None:
    tools = [
        Tool(
            function=ToolFunction(
                name="get_weather",
                description="Wetter abfragen",
                parameters={"type": "object", "properties": {"city": {"type": "string"}}},
            )
        )
    ]
    result = _tools_param(tools)
    assert result == [
        {
            "name": "get_weather",
            "description": "Wetter abfragen",
            "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
        }
    ]


def test_tool_choice_auto_and_named_function() -> None:
    assert _tool_choice_param("auto") == {"type": "auto"}
    assert _tool_choice_param("required") == {"type": "any"}
    named = _tool_choice_param({"type": "function", "function": {"name": "get_weather"}})
    assert named == {"type": "tool", "name": "get_weather"}
