# FreshBrain AI Engine

FastAPI service for FreshBrain chat orchestration, conversation persistence,
feedback, and internal data tools.

## Local development

Requires Python 3.12+, PostgreSQL, and Redis (currently used only for rate
limiting — no cache, locks, or queue backend yet; that's a scoping choice for
now, not a rule against ever using Redis for those later).

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
docker compose -f ../freshbrain-ai-engine-db/docker-compose.yml up -d
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

In a second terminal, run the background worker (polls for jobs — currently
just rolling conversation summarization, see below):

```bash
.venv/bin/python -m app.worker
```

The Claude and WMS integrations default to explicit stub behavior. Set
`STUB_CLAUDE_API=false` to use Anthropic after configuring an API key. WMS
continues to return stub data until its endpoint contract and credentials are
configured.

If the database was created from the former `db/schema.sql`, use
`.venv/bin/alembic stamp 0001` once instead of applying the initial migration.

### Auth (self-issued, until chat-gateway is in the live path)

Every endpoint except `POST /dev/token` requires a real HS256-signed JWT —
`app/core/security.py` verifies it, no gateway involved. Generate a real
`JWT_SECRET` for your `.env` with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

To call the API from `/docs`: open Swagger, expand `POST /dev/token`, mint a
token with `{"user_id": "<uuid>", "role": "Superuser", "allowed_scopes": [...]}`
(`user_id` must be a real UUID — it's stored as one), copy `access_token`,
click the "Authorize" padlock, paste it in. From then on every request in
that Swagger session goes out with it attached. `/dev/token` is a stand-in
for chat-gateway signing real tokens — delete it (and switch `get_current_claims`
to verify gateway's signature instead) once chat-gateway is wired into the
live path (v0.5.0 Beta — see `freshbrain-agreement/VERSIONING.md`).

### Rolling conversation summarization

`ChatService.chat()` no longer sends a conversation's full message history to
Claude. Once a conversation passes `SUMMARY_TRIGGER_MESSAGES` (default 40)
total messages, it enqueues a `summarize_conversation` background job every
`CONTEXT_WINDOW_MESSAGES` (default 20) messages; the worker folds the
newly-aged-out messages into `conversations.rolling_summary`. Every `/chat`
request then sends `rolling_summary` (if present) plus the last
`CONTEXT_WINDOW_MESSAGES` raw messages instead of the whole history — see
`app/chat/context.py`'s `build_chat_context()`.

The job queue (`background_jobs` table, `app/worker/`) is Postgres-backed,
not Redis — claimed via `SELECT ... FOR UPDATE SKIP LOCKED`, deduplicated via
a partial unique index on `(job_type, payload->>'conversation_id') WHERE
status = 'pending'`. No retry/backoff beyond a basic `attempts` counter, no
job lease/timeout, no multi-worker coordination beyond `SKIP LOCKED` — a
worker crash mid-job leaves it stuck in `processing` with no automatic
reclaim, which is an accepted gap at this stage, not an oversight.

### Rate limiting

`POST /dev/token`, `POST /chat`, and `POST /chat/title` are rate limited
(`slowapi`, Redis-backed storage, per-IP) — see `app/core/rate_limit.py` and
`DEV_TOKEN_RATE_LIMIT`/`CHAT_RATE_LIMIT` in `.env.example`. `/dev/token` is
limited tighter (5/minute) since it's unauthenticated and otherwise
spammable; `/chat`/`/chat/title` protect the paid Claude API.

### Logging

Structured (JSON) logging via `structlog`, configured once in
`app/core/logging.py` and installed on the root logger's handler — existing
bare `logging.getLogger(__name__)` call sites elsewhere in the app need no
changes to get JSON output. `app/core/request_logging.py`'s middleware binds
a `request_id` per request and logs start/completion with method, path,
status, and duration. No OpenTelemetry/distributed tracing yet — revisit once
there's more than this one service to trace across.

## Structure

```text
app/
├── chat/             # routes, application workflow, model loop, and tools
├── conversations/    # schemas, service, repository, and ORM models
├── core/             # settings, database lifecycle, auth, logging, rate limiting
├── feedback/         # schemas, service, repository, and ORM model
├── integrations/     # Anthropic, warehouse, and WMS clients
└── worker/           # Postgres-backed background job queue + poll loop
```

Routers handle HTTP concerns, services coordinate application behavior,
repositories contain persistence queries, and integrations own external I/O.

## Checks

Requires the local Postgres up (`tests/conftest.py`'s `db_session` fixture
runs against it, wrapped in a rolled-back transaction per test) — this
wasn't needed before the background worker's tests were added.

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```
