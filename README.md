# AI Gateway

Production-grade **AI Gateway** — ein einheitlicher Einstiegspunkt für mehrere
LLM-Provider (OpenAI, Anthropic, Grok, lokale Modelle u. a.) mit Routing,
Fallback-Logik, Tool Calling, RAG, Usage-/Kosten-Tracking, API-Key-
Authentifizierung und einer OpenAI-kompatiblen Chat Completions API
(REST + Streaming + WebSocket).

## Features

- OpenAI-kompatible Chat Completions API (`/api/v1/chat/completions`), inkl. Streaming (SSE)
- WebSocket-Chat (`/api/v1/chat/ws`) für persistente Multi-Turn-Sessions
- Multi-Provider-Routing mit automatischem Fallback (OpenAI, Anthropic, Grok, lokale Modelle)
- Tool Calling / Function Calling (provider-übergreifend normalisiert)
- Basic-RAG-Modul (`/api/v1/rag/*`) — Dokumente einbetten und in Chats einbeziehen
- API-Key-Auth, Rate Limiting, strukturiertes Logging, Usage-/Kosten-Tracking
- Admin-API + Admin-Panel (SQLAdmin) unter `/admin-panel`
- Minimale statische Demo-UI unter `/app`
- Vollständige Testsuite + CI (GitHub Actions)

## Schnellstart mit Docker (empfohlen für Deployment)

```bash
git clone https://github.com/bagdanchik007/ai-gateway.git
cd ai-gateway
cp .env.example .env
# .env bearbeiten: SECRET_KEY, ADMIN_PANEL_SECRET, mind. einen Provider-Key setzen

docker compose up -d --build
docker compose exec app alembic upgrade head
```

Danach erreichbar unter:
- API-Doku: http://localhost:8000/docs
- Demo-Chat-UI: http://localhost:8000/app/
- Admin-Panel: http://localhost:8000/admin-panel
- Health-Check: http://localhost:8000/health

Einen ersten Admin-User + API-Key anlegen (Admin-Flag muss danach manuell in
der DB gesetzt werden, siehe `docs/API.md`):

```bash
curl -X POST http://localhost:8000/api/v1/admin/api-keys \
  -H "Content-Type: application/json" \
  -d '{"user_email": "admin@example.com", "name": "erster-key"}'
```

## Lokale Entwicklung ohne Docker

```bash
poetry install
cp .env.example .env
docker compose up -d db redis   # nur DB + Redis in Containern
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

## Tests

```bash
poetry run pytest tests/ -v
poetry run ruff check app/ tests/
poetry run mypy app/
```

## Weiterführende Doku

Siehe [`docs/API.md`](docs/API.md) für Endpoint-Referenz, Auth-Fluss,
Fehlerformat und End-to-End-Beispiele (inkl. Streaming, Tool Calling, RAG,
Fallback-Ketten).

## Architektur

```
app/
├── api/v1/          # HTTP- und WebSocket-Routen
├── admin/            # SQLAdmin-Panel (Views, Auth)
├── core/             # Konfiguration, Security, Middleware, Logging, Exceptions
├── providers/        # Adapter für LLM-Provider (base.py + openai.py, anthropic.py)
├── services/         # Business-Logik: llm_router, prompt_engine, memory, rag/, usage_tracker
├── db/               # SQLAlchemy Engine/Session, Modelle
└── schemas/          # Pydantic-Schemas

frontend/              # Statische Demo-Chat-UI (kein Build-Schritt)
tests/                  # Unit- und Integrationstests
alembic/                # DB-Migrationen
.github/workflows/      # CI (Lint, Type-Check, Migrationen, Tests)
```

## Lizenz

MIT
