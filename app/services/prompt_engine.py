"""Prompt-Engineering-Service."""

import structlog
import tiktoken

from app.schemas.llm import ChatCompletionRequest, ChatMessage

logger = structlog.get_logger(__name__)

_DEFAULT_SYSTEM_PROMPT = "Du bist ein hilfreicher Assistent."
_DEFAULT_TOKEN_BUDGET = 8000
_ENCODING_NAME = "cl100k_base"
_encoding: tiktoken.Encoding | None = None
_tiktoken_unavailable = False


def _get_encoding() -> tiktoken.Encoding | None:
    global _encoding, _tiktoken_unavailable
    if _encoding is None and not _tiktoken_unavailable:
        try:
            _encoding = tiktoken.get_encoding(_ENCODING_NAME)
        except Exception as exc:
            _tiktoken_unavailable = True
            logger.warning("prompt_engine.tiktoken_unavailable", error=str(exc))
    return _encoding


def count_tokens(text: str) -> int:
    encoding = _get_encoding()
    if encoding is not None:
        return len(encoding.encode(text))
    return max(1, len(text) // 4)


def apply_prompt_engineering(
    request: ChatCompletionRequest,
    token_budget: int = _DEFAULT_TOKEN_BUDGET,
) -> ChatCompletionRequest:
    messages = list(request.messages)

    if not any(m.role == "system" for m in messages):
        messages.insert(0, ChatMessage(role="system", content=_DEFAULT_SYSTEM_PROMPT))

    messages = _truncate_to_budget(messages, token_budget)

    return request.model_copy(update={"messages": messages})


def _truncate_to_budget(messages: list[ChatMessage], token_budget: int) -> list[ChatMessage]:
    system_messages = [m for m in messages if m.role == "system"]
    other_messages = [m for m in messages if m.role != "system"]

    used = sum(count_tokens(m.content or "") for m in system_messages)
    kept: list[ChatMessage] = []
    for message in reversed(other_messages):
        cost = count_tokens(message.content or "")
        if used + cost > token_budget and kept:
            break
        used += cost
        kept.insert(0, message)

    return [*system_messages, *kept]
