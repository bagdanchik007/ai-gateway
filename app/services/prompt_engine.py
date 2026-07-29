"""Prompt-Engineering-Service.

Bereitet eine Chat-Anfrage auf, bevor sie an einen Provider geht:
- setzt einen Default-System-Prompt, falls keiner mitgeschickt wurde
- kürzt die Historie auf ein Token-Budget (Schätzung per tiktoken), damit
  lange Chat-Verläufe nicht an der Context-Window-Grenze des Providers scheitern
Router und Provider bekommen davon nichts mit — sie sehen nur das fertige
ChatCompletionRequest, genau wie ohne diesen Service.
"""

import structlog
import tiktoken

from app.schemas.llm import ChatCompletionRequest, ChatMessage

logger = structlog.get_logger(__name__)

_DEFAULT_SYSTEM_PROMPT = "Du bist ein hilfreicher Assistent."
_DEFAULT_TOKEN_BUDGET = 8000

# cl100k_base ist die Encoding-Familie moderner OpenAI-Modelle. Für andere
# Provider (Anthropic, Grok, lokal) ist das nur eine Näherung, aber deutlich
# besser als eine reine Zeichen-/Wortzahl-Heuristik.
_ENCODING_NAME = "cl100k_base"
_encoding: tiktoken.Encoding | None = None
_tiktoken_unavailable = False


def _get_encoding() -> tiktoken.Encoding | None:
    """Lädt das tiktoken-Encoding lazy und cached es.

    tiktoken lädt seine BPE-Datei beim ersten Gebrauch per HTTP nach
    (openaipublic.blob.core.windows.net) — in Netzwerken mit restriktiven
    Egress-Regeln (z. B. Firmen-Proxies, gehärtete Produktionsumgebungen)
    kann das fehlschlagen. Statt das Gateway deswegen abstürzen zu lassen,
    fällt `_count_tokens` dann auf eine grobe Zeichen-Heuristik zurück.
    """
    global _encoding, _tiktoken_unavailable
    if _encoding is None and not _tiktoken_unavailable:
        try:
            _encoding = tiktoken.get_encoding(_ENCODING_NAME)
        except Exception as exc:
            _tiktoken_unavailable = True
            logger.warning("prompt_engine.tiktoken_unavailable", error=str(exc))
    return _encoding


def _count_tokens(text: str) -> int:
    encoding = _get_encoding()
    if encoding is not None:
        return len(encoding.encode(text))
    # Grobe Offline-Heuristik: ~4 Zeichen pro Token für deutschen/englischen
    # Fließtext. Ungenauer als tiktoken, aber funktioniert ohne Netzwerkzugriff.
    return max(1, len(text) // 4)


def apply_prompt_engineering(
    request: ChatCompletionRequest,
    token_budget: int = _DEFAULT_TOKEN_BUDGET,
) -> ChatCompletionRequest:
    """Gibt eine neue Request-Instanz mit Default-System-Prompt und gekürzter Historie zurück."""
    messages = list(request.messages)

    if not any(m.role == "system" for m in messages):
        messages.insert(0, ChatMessage(role="system", content=_DEFAULT_SYSTEM_PROMPT))

    messages = _truncate_to_budget(messages, token_budget)

    return request.model_copy(update={"messages": messages})


def _truncate_to_budget(messages: list[ChatMessage], token_budget: int) -> list[ChatMessage]:
    """Behält alle System-Messages und so viele der jüngsten übrigen Nachrichten wie ins Budget passen.

    Ältere User/Assistant-Nachrichten werden verworfen statt zusammengefasst.
    Eine echte Zusammenfassung (Summarization) ist ein Kandidat für einen
    eigenen Ausbauschritt, sobald der Bedarf in der Praxis auftritt.
    """
    system_messages = [m for m in messages if m.role == "system"]
    other_messages = [m for m in messages if m.role != "system"]

    used = sum(_count_tokens(m.content) for m in system_messages)
    kept: list[ChatMessage] = []
    for message in reversed(other_messages):
        cost = _count_tokens(message.content)
        if used + cost > token_budget and kept:
            break
        used += cost
        kept.insert(0, message)

    return [*system_messages, *kept]
