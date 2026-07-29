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
