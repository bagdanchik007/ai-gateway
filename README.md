# AI Gateway

Production-grade **AI Gateway** — ein einheitlicher Einstiegspunkt für mehrere
LLM-Provider (OpenAI, Anthropic, Grok, lokale Modelle u. a.) mit Routing,
Fallback-Logik, Usage-/Kosten-Tracking, API-Key-Authentifizierung und einer
OpenAI-kompatiblen Chat Completions API.

Das ist kein reiner Proxy: das Gateway bringt eine Prompt-Engineering-Schicht,
Chat-Memory, Usage-Tracking und Rate-Limiting mit und ist von Anfang an für
Tool Calling / RAG / Multi-Agent-Szenarien ausgelegt.

## Kernprinzipien

- **Async-first**: sämtliches I/O (DB, HTTP zu den Providern, Redis) ist asynchron.
- **Clean Architecture**: strikte Trennung der Schichten — API / services / providers / db.
- **Erweiterbarkeit**: ein neuer LLM-Provider = eine neue Klasse, die `BaseLLMProvider`
  implementiert, ohne Änderungen am restlichen Code.
- **Production-ready von Anfang an**: Typisierung (Pydantic v2), Error Handling,
  strukturiertes Logging, Tests, CI.

## Stack

| Schicht          | Technologie                          |
|------------------|---------------------------------------|
| Sprache          | Python 3.12                          |
| Web-Framework    | FastAPI                              |
| Validierung      | Pydantic v2 / pydantic-settings      |
| Datenbank        | PostgreSQL + SQLAlchemy 2.0 (async)  |
| Migrationen      | Alembic                              |
| Cache / Limits   | Redis                                |
| Dependencies     | Poetry                               |
| Containerisierung| Docker / docker-compose              |

## Projektstruktur

```
app/
├── api/v1/          # HTTP-Routen (versioniert), dünne Schicht — nur I/O und Service-Aufrufe
├── core/             # Konfiguration, Security, Middleware, allgemeine App-Settings
├── providers/        # Adapter für LLM-Provider (base.py + openai.py, anthropic.py, grok.py, ...)
├── services/         # Business-Logik: llm_router, prompt_engine, memory, usage_tracker
├── db/               # SQLAlchemy Engine/Session, Modelle
├── schemas/          # Pydantic-Schemas für Requests/Responses
└── utils/            # Allgemeine Helper ohne Business-Logik

tests/
├── unit/
└── integration/

alembic/              # DB-Migrationen
```

### Warum so

- **`providers/`** isoliert die Eigenheiten jedes Anbieters (Request-Formate, Streaming,
  Tokenizer) hinter einem einheitlichen `BaseLLMProvider`-Interface. Ein neuer Provider
  ändert weder `api/` noch `services/`.
- **`services/llm_router`** entscheidet, welcher Provider/Model die Anfrage bedient, und
  enthält die Fallback-Logik (Retry auf einen anderen Provider bei Fehler/Nichtverfügbarkeit).
- **`api/v1`** enthält keine Business-Logik — nur Input-Validierung, Service-Aufruf und
  Response-Aufbau. So lässt sich künftig problemlos ein `v2` hinzufügen, ohne Logik zu duplizieren.

## Roadmap

Das Projekt entsteht schrittweise (siehe `ROADMAP.md` / git log für die Commit-Historie):

0. **Projekt-Initialisierung** — Struktur, Poetry, Docker, Config, Health Check
1. **Foundation & Auth** — DB, Modelle, API-Key-Authentifizierung, Rate Limiting
2. **LLM Providers** — Basis-Interface, OpenAI/Anthropic/Grok/lokal, Routing mit Fallback
3. **Chat API** — OpenAI-kompatibler Endpoint, Streaming, Prompt Engineering, Chat-Memory
4. **Usage & Monitoring** — Usage-/Kosten-Tracking, Logging
5. **Polish & Admin** — Admin-Panel, Error Handling, Dokumentation, Tests und CI
6. **Advanced** — Tool Calling, RAG, WebSocket-Chat, Frontend

## Quickstart (entsteht mit dem Projektfortschritt)

```bash
poetry install
cp .env.example .env
docker-compose up -d db redis
poetry run uvicorn app.main:app --reload
```

## Lizenz

TBD
