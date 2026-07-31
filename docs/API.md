# AI Gateway — API-Dokumentation

Interaktive Doku (Swagger UI) läuft unter `/docs`, das rohe OpenAPI-Schema
unter `/openapi.json`. Dieses Dokument ergänzt das um Kontext, den eine
generierte Spezifikation nicht transportiert (Auth-Fluss, Fehlerformat,
End-to-End-Beispiele).

## Authentifizierung

Alle Endpoints unter `/api/v1/chat/*` und `/api/v1/admin/*` erfordern:

```
Authorization: Bearer <api-key>
```

API-Keys werden ausschließlich über `POST /api/v1/admin/api-keys` erzeugt
(erfordert selbst einen Admin-Key) und genau einmal im Klartext zurückgegeben.

## Fehlerformat

Jeder Fehler hat dieselbe Form (siehe `app/core/exception_handlers.py`):

```json
{
  "error": {
    "message": "Alle Provider in der Kette sind fehlgeschlagen oder nicht konfiguriert: ['x:y']",
    "type": "no_provider_available",
    "status_code": 503
  }
}
```

| `type`                          | Status | Bedeutung                                                    |
|---------------------------------|--------|---------------------------------------------------------------|
| `validation_error`               | 422    | Request-Body entspricht nicht dem Schema                       |
| `http_error`                     | variabel | z. B. 401 bei fehlendem/ungültigem API-Key, 403 bei fehlender Admin-Rolle |
| `provider_authentication_error`  | 502    | Der *Provider*-Key (OpenAI/Anthropic/…) ist ungültig — Server-Fehlkonfiguration |
| `model_not_found`                | 404    | Angefordertes Modell existiert beim Provider nicht              |
| `no_provider_available`          | 503    | Alle Provider in der Fallback-Kette sind fehlgeschlagen oder nicht konfiguriert |
| `provider_error`                 | 502    | Sonstiger Provider-Fehler (z. B. Timeout, 5xx vom Provider)     |
| `internal_error`                 | 500    | Unerwarteter Fehler — Details landen im Server-Log, nie in der Response |

Bei **Streaming**-Antworten (`stream: true`) ist der HTTP-Status bereits `200`,
bevor ein Fehler auftreten kann — Fehler erscheinen dort stattdessen als
letztes SSE-Event mit einem `error`-Feld, gefolgt von `data: [DONE]`.

## Chat Completions

`POST /api/v1/chat/completions` — OpenAI-kompatibel, mit drei
Gateway-spezifischen Erweiterungen (werden von echten OpenAI-Clients
einfach ignoriert):

- **`fallback_models`**: Liste weiterer `"<provider>:<model>"`-IDs. Schlägt
  der primäre Provider mit einem transienten Fehler fehl (Rate Limit,
  Timeout, Unavailable), wird automatisch der nächste versucht.
- **`conversation_id`**: Wenn gesetzt, wird die serverseitig in Redis
  gespeicherte Historie vorangestellt — der Client muss dann nicht bei
  jedem Request den kompletten Verlauf mitschicken.
- Modell-IDs folgen immer dem Schema **`<provider>:<model>`**, z. B.
  `openai:gpt-4o-mini`, `anthropic:claude-3-5-sonnet-20241022`,
  `grok:grok-2-latest`, `local:llama3`.

### Beispiel: einfacher Request

```bash
curl -s https://<host>/api/v1/chat/completions \
  -H "Authorization: Bearer sk-gw-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai:gpt-4o-mini",
    "messages": [{"role": "user", "content": "Erkläre mir Kubernetes in 2 Sätzen."}]
  }'
```

### Beispiel: mit Fallback-Kette

```bash
curl -s https://<host>/api/v1/chat/completions \
  -H "Authorization: Bearer sk-gw-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai:gpt-4o-mini",
    "fallback_models": ["anthropic:claude-3-5-haiku-20241022"],
    "messages": [{"role": "user", "content": "Hallo!"}]
  }'
```

### Beispiel: Streaming

```bash
curl -N https://<host>/api/v1/chat/completions \
  -H "Authorization: Bearer sk-gw-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai:gpt-4o-mini",
    "stream": true,
    "messages": [{"role": "user", "content": "Zähl von 1 bis 5."}]
  }'
```

### Beispiel: mit Server-seitiger Historie

```bash
# Erster Request: legt die Konversation an
curl -s https://<host>/api/v1/chat/completions \
  -H "Authorization: Bearer sk-gw-..." -H "Content-Type: application/json" \
  -d '{"model": "openai:gpt-4o-mini", "conversation_id": "chat-42", "messages": [{"role": "user", "content": "Ich heiße Bohdan."}]}'

# Zweiter Request: sieht die vorherige Nachricht automatisch
curl -s https://<host>/api/v1/chat/completions \
  -H "Authorization: Bearer sk-gw-..." -H "Content-Type: application/json" \
  -d '{"model": "openai:gpt-4o-mini", "conversation_id": "chat-42", "messages": [{"role": "user", "content": "Wie heiße ich?"}]}'
```

## Admin-Endpoints

Erfordern einen API-Key eines Users mit `is_admin=true`.

| Methode  | Pfad                        | Zweck                                         |
|----------|-----------------------------|------------------------------------------------|
| `POST`   | `/api/v1/admin/api-keys`    | Neuen API-Key erzeugen (legt User bei Bedarf an) |
| `GET`    | `/api/v1/admin/api-keys`    | Alle API-Keys auflisten                        |
| `DELETE` | `/api/v1/admin/api-keys/{id}` | Key widerrufen (soft delete, `is_active=false`) |
| `GET`    | `/api/v1/admin/usage`       | Aggregierte Usage-Statistik nach Provider/Modell |

Eine visuelle Alternative zur API gibt es unter `/admin-panel` (SQLAdmin,
eigenes Passwort-Login über `ADMIN_PANEL_SECRET`).

## Health Check

`GET /health` — kein Auth nötig, vom Rate Limiting ausgenommen. Für
Docker-/Kubernetes-Liveness-/Readiness-Probes gedacht.
