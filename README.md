# FreshBrain AI Engine

FastAPI service for FreshBrain chat orchestration, conversation persistence,
feedback, and internal data tools.

## Local development

Requires Python 3.12+ and PostgreSQL.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
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

## Structure

```text
app/
├── chat/             # routes, application workflow, model loop, and tools
├── conversations/    # schemas, service, repository, and ORM models
├── core/             # settings, database lifecycle, and temporary auth
├── feedback/         # schemas, service, repository, and ORM model
└── integrations/     # Anthropic, warehouse, and WMS clients
```

Routers handle HTTP concerns, services coordinate application behavior,
repositories contain persistence queries, and integrations own external I/O.

## Checks

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```
