# Job Search Workflow Bot

**Durable Telegram automation for vacancy analysis and cover-letter drafts**

[![CI](https://github.com/Unequal1213/ai-job-search-assistant-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Unequal1213/ai-job-search-assistant-bot/actions/workflows/ci.yml)

Job Search Workflow Bot is an aiogram polling service that preserves Telegram
workflow state in PostgreSQL. It analyzes vacancy text with deterministic local
keyword rules and creates a short template-based cover-letter draft. The
workflow layer adds user/chat isolation, idempotent Telegram update processing,
persisted limits, and an append-only audit trail.

The historical repository name is `ai-job-search-assistant-bot`. The public
Phase 3B1 name reflects what the current implementation can demonstrate.

## Current AI status

The current provider is deterministic and offline. A real LLM provider is
intentionally deferred to a separately controlled phase.

No external model credentials, token counts, model calls, or fallback claims
exist in Phase 3B1. Provider metadata truthfully records:

- `provider_requested=deterministic`
- `provider_used=deterministic`
- `provider_kind=offline_rules`
- `provider_version=rules-v1` by default
- `fallback_used=false`

## Bot commands

- `/start` — introduces the bot.
- `/help` — lists the available commands.
- `/analyze_vacancy` — asks for vacancy text and returns role, seniority,
  required skills, matching keywords, and a recommendation.
- `/generate_cover_letter` — asks for vacancy text and returns a short
  template-based draft.

The command names and two-step FSM flows are preserved from the initial MVP.
aiogram FSM state is only conversation UX state; it is not treated as durable
business state.

## Architecture

```text
Telegram update
  -> aiogram handler (minimal user/chat/update identifiers)
  -> WorkflowService (validation, idempotency, admission, transitions)
  -> actor-scoped repositories and persisted limits
  -> deterministic offline provider
  -> PostgreSQL result and audit event
  -> safe Telegram response formatter
```

```text
app/
  bot/                 dispatcher and isolated in-memory FSM boundary
  core/                typed settings, limits, safe errors, structured logging
  db/
    models/            typed SQLAlchemy models
    repositories/      actor-scoped persistence operations
    session.py         async engine/session lifecycle
  handlers/            thin Telegram command and FSM handlers
  providers/           protocols and deterministic implementations
  schemas/             strict Pydantic boundary/result models
  services/            workflow, rate-limit, analysis, and draft services
  main.py              startup, connectivity check, polling, shutdown
migrations/            explicit Alembic migration history
tests/                 unit, boundary, persistence, race, and PostgreSQL tests
```

Handlers do not execute SQL or contain vacancy analysis rules. Raw message text
is passed to `WorkflowService`, used in memory for one deterministic operation,
and then discarded.

## Durable workflow states

Allowed transitions are explicit:

```text
received -> processing -> completed
                       -> failed
received -> rejected
received -> rate_limited
```

Every transition validates the current status, updates timestamps, and appends
a `workflow_events` row in the same transaction. Terminal workflows cannot be
reprocessed; a new Telegram update creates a new workflow attempt.

Admission and completion use separate transactions. This makes `processing`
visible while work is active, so a second request for the same actor can be
rejected by the per-actor concurrency limit without blocking unrelated actors.

## Persistence model

- `telegram_actors` stores only an internal UUID plus the unique pair
  `(telegram_user_id, telegram_chat_id)` and timestamps.
- `workflow_runs` stores operation/state, Telegram update id, SHA-256 input
  fingerprint, character count, provider metadata, safe result JSON, error
  category, and timestamps.
- `workflow_events` stores state changes and allowlisted safe metadata.
- `usage_windows` stores restart-safe fixed-window counters per actor and
  operation.

`(telegram_chat_id, telegram_update_id)` is unique. A repeated update returns
the known safe result when available, creates no second run, consumes no extra
quota, and appends a duplicate event without the raw update payload. PostgreSQL
row locks serialize admission for one actor; database constraints remain the
final race-safety boundary.

## Data retention policy

Phase 3B1 does **not** persist raw vacancy text, cover-letter input, Telegram
message text, usernames, names, phone numbers, email addresses, bot tokens, or
raw update payloads.

Persisted input metadata is limited to a SHA-256 fingerprint and character
count. Structured analysis and the generated template draft are persisted so
an idempotent retry can return the already known result. No automatic database
retention/deletion job is implemented in this phase; operators must define a
workflow-result retention period before any real-user use.

## Controls and safe errors

Typed settings have conservative defaults and validation bounds:

| Setting | Default |
| --- | ---: |
| `MAX_VACANCY_TEXT_CHARS` | 12000 |
| `MAX_COVER_LETTER_CONTEXT_CHARS` | 8000 |
| `MAX_MESSAGE_CHARS` | 12000 |
| `MAX_ACTIVE_WORKFLOWS_PER_ACTOR` | 1 |
| `WORKFLOW_TIMEOUT_SECONDS` | 120 |
| `RATE_LIMIT_WINDOW_SECONDS` | 60 |
| `RATE_LIMIT_REQUESTS_PER_WINDOW` | 5 |

Input checks run before business processing and quota consumption. Persisted
rate limits are separated by actor and operation. Stable error categories are
`invalid_input`, `input_too_large`, `rate_limited`, `concurrent_request`,
`duplicate_update`, `persistence_error`, and `internal_error`.

User responses never contain SQL, DSNs, stack traces, credentials, or reflected
message content.

## Safe logging

Application events use an explicit allowlist: event, internal workflow/actor
UUID, operation, status, input character count, provider used, error category,
latency, and Telegram update id. Raw message text, generated content, usernames,
contact details, tokens, database passwords, and complete updates are excluded.

The test suite injects synthetic sensitive markers and verifies that captured
logs and event metadata do not contain them.

## Requirements and locked installation

Supported Python range: **3.11 through 3.13** (`>=3.11,<3.14`). CI and Docker
use Python 3.13.

- `requirements.in` contains direct runtime dependency ranges.
- `requirements.txt` is the exact resolved runtime lock used by Docker.
- `requirements-dev.in` adds test, lint, SQLite-unit-test, and audit tooling.
- `requirements-dev.txt` is the exact resolved CI/development lock.

Create an isolated environment and install the dev lock:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

To intentionally update locks, use an isolated tool environment with
`pip-tools==7.6.0` and its supported `pip==25.3`, review the diff, and run every
gate again:

```bash
python -m piptools compile --strip-extras -o requirements.txt requirements.in
python -m piptools compile --strip-extras -o requirements-dev.txt requirements-dev.in
```

Dependencies come from the default official PyPI index. The project contains
no Git or direct-URL dependencies.

## Configuration

Copy `.env.example` for local use and replace placeholders. Never commit the
resulting `.env`.

Required runtime setting:

- `DATABASE_URL`, using the `postgresql+asyncpg://` scheme.

Optional settings include `BOT_TOKEN`, `ENVIRONMENT`, `LOG_LEVEL`, the limits
listed above, and `DETERMINISTIC_PROVIDER_VERSION`. Token and database URL
values use Pydantic `SecretStr` and are excluded from normal representations.

`BOT_TOKEN` is needed only for deliberate Telegram polling. Tests, migrations,
audits, config smoke checks, and CI do not require it.

## Migrations

Schema changes are never applied during import or application startup. Set a
disposable/local `DATABASE_URL` and run migrations explicitly:

```bash
python -m alembic upgrade head
python -m alembic check
```

The initial migration creates PostgreSQL enums, tables, foreign keys, indexes,
unique constraints, JSONB result/event fields, and server-side timestamp
defaults. Its downgrade is tested only against disposable databases.

## Tests

Fast tests use SQLite only where behavior is database-independent:

```bash
python -m ruff check .
python -m pytest -m "not postgres"
```

PostgreSQL tests use the separate disposable profile and synthetic credentials:

```bash
docker compose -f docker-compose.test.yml up -d postgres-test
export DATABASE_URL=postgresql+asyncpg://workflow_test:synthetic_test_only@127.0.0.1:55432/workflow_test
export TEST_DATABASE_URL="$DATABASE_URL"
python -m alembic upgrade head
python -m alembic check
python -m pytest
docker compose -f docker-compose.test.yml down
```

The PostgreSQL suite verifies migrations, actor isolation, persistence after
engine recreation, unique constraints, idempotent duplicate races, persisted
quota, per-actor concurrency, and non-blocking behavior for another actor. All
fixtures and vacancy text are synthetic. No Telegram network call is made.

## Docker and Compose

The runtime image:

- uses `python:3.13-slim-bookworm`;
- installs only the exact runtime lock;
- excludes `.env`, tests, VCS data, and local caches from build context;
- runs as non-root UID/GID `10001:10001`;
- starts polling only through `python -m app.main` after configuration and DB
  connectivity succeed.

Main Compose includes the bot and PostgreSQL 17.6, a PostgreSQL healthcheck, a
named database volume, and healthy dependency ordering. The database has no
host port by default. `restart: unless-stopped` is intended for local service
recovery, not as a deployment policy.

Build and validate without Telegram access:

```bash
docker compose build
docker run --rm \
  -e DATABASE_URL=postgresql+asyncpg://placeholder:placeholder@db:5432/placeholder \
  --entrypoint python ai-job-search-assistant-bot-bot -m app.config_check
```

The config check validates settings only; it does not connect to PostgreSQL or
Telegram. Migrations remain a separate command.

## CI

GitHub Actions has read-only `contents` permission and uses official
`actions/checkout@v7` and `actions/setup-python@v6`. CI installs the dev lock,
runs `pip check`, Ruff, a fresh PostgreSQL migration, `alembic check`, the full
test suite, production dependency audit, current-tree secret-pattern scan,
Compose validation, Docker build, non-root assertion, offline config smoke, and
an image filesystem `.env` assertion.

CI has no Telegram token, model key, PAT, deployment permission, registry push,
or write permission.

## Security limitations

- aiogram FSM storage is in memory and intentionally used only for dialogue UX;
  an interrupted prompt is not resumed after process restart.
- Telegram long polling is a single service instance in this phase; distributed
  polling ownership is not implemented.
- Fixed-window rate limiting is intentionally simple and is not a substitute
  for upstream abuse controls.
- Application-level encryption for persisted structured results is not present.
- Automated retention cleanup, backup policy, monitoring, alerting, and
  operational incident procedures are outside Phase 3B1.
- Dependency audit reports known advisories in the selected database; it does
  not prove the absence of all security defects.
- No external deployment or real-user workload has been validated.

## Synthetic demo policy

Screenshots and tests use fictional vacancy text and synthetic identifiers.
Do not place client data, real Telegram updates, contact details, credentials,
or copied private vacancies in fixtures, logs, screenshots, or CI artifacts.

## Roadmap: Phase 3B2

Phase 3B2 may add one real LLM implementation only behind the existing strict
provider contracts and only through a separately controlled credential and
smoke-test process. Phase 3B2 must preserve deterministic providers for tests,
durable workflow controls, idempotency, safe logging, and the no-raw-input
storage policy. It is intentionally not part of this phase.
