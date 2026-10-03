# Rick and Morty Portal

Two Persian Telegram assistants for private administration, sourced news,
verified market reports and reviewed channel posts. Rick is sarcastic and
analytical; Morty is nervous, friendly and practical. Their system prompts,
responses, reactions and channel presentation are editable database records.

## Components

| Directory | Responsibility |
| --- | --- |
| `api` | Papilio API, domain workflows, MySQL persistence and Papilio Tasks |
| `bots` | aiogram webhooks, private admin commands and Telegram delivery |
| `packages/contracts` | Typed contracts shared by both applications |
| `deploy` | Compose release, backups and restricted Nginx ingress |

MySQL owns configuration, missions, collected evidence, drafts, approvals,
publication reservations and model costs. Redis carries native Papilio Tasks.
The model can read permitted evidence and create drafts. Channel publication
requires a human approval for the current draft revision.

## Start locally

Requirements: Python 3.13, Docker with Compose v2, two distinct Telegram bot
tokens, an OpenRouter key and numeric administrator IDs.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r api/requirements-dev.lock -r bots/requirements.lock
.venv/bin/python -m pip install --no-deps -e packages/contracts -e api -e bots
.venv/bin/python -m pip check
cp .env.example .env
# Fill the three original bot/model credentials in .env.
.venv/bin/python tools/prepare_env.py
# Set PORTAL_ADMIN_USER_IDS in the private .env.runtime if it is still empty.
docker compose --env-file .env.runtime up -d --build
```

`prepare_env.py` retains the original `.env`, generates independent service,
webhook and database credentials, and creates a minimal `config.yml`. It reads
the optional local Papilio Proxy environment for the admin allowlist. Both
generated files are ignored. Compose runs a forward Alembic migration and an
idempotent seed before starting the API, worker, scheduler and bots.

Incoming Telegram messages need public HTTPS. Use the deployment instructions
to serve `bot.amupouya.org`; then register the two distinct webhook paths:

```bash
docker compose --env-file .env.runtime exec -T bots python -m portal_bots.webhooks
```

Start both bots in a private chat using `/start`. Add both as channel admins
with permission to post before enabling channel delivery. Polling must not run
for these tokens while webhooks are active.

## Commands

| Command | Result |
| --- | --- |
| `/ask rick text`, `/ask morty text` | A bounded assistant mission |
| `/team text`, `/news python ai` | Collected article evidence and a news draft |
| `/summarize https://...` | Read an allowed source and draft its summary |
| `/prices` | Fetch all three fresh quotes and prepare a market draft |
| `/jobs [page]`, `/job id`, `/cancel id` | Inspect or cancel owned missions |
| `/drafts [page]`, `/draft id` | Inspect draft content and its revision |
| `/approve id [revision]`, `/reject id [revision]` | Decide on a specific revision |
| `/publish id` | Preview and explicitly confirm channel delivery |
| `/schedule id ISO-timestamp` | Schedule an approved revision |
| `/add_music text`, `/add_tech text`, `/notice text` | Create a manual draft |
| `/status`, `/pause`, `/resume` | Inspect health, queues, cost reservations and publishing |
| `/resolve publication-id message-id` | Record a confirmed ambiguous delivery |
| `/resolve publication-id resend` | Explicitly authorize a new attempt |
| `/settings key scope` | Read a database setting and revision |
| `/set_setting key scope JSON` | Validate and update that database record |
| `/prompt [text]` | Read or update the receiving persona's system prompt |

Responses and draft notifications return through the originating bot. Every
command is restricted to allowlisted administrators in private chats.

## Configuration and OpenRouter

Business configuration is stored in MySQL using separate setting definitions
and scoped values, plus news sources and their configurations. The initial
`api/seeds/defaults.json` creates missing records; restarting or seeding never
overwrites administrator changes. Credentials and transport belong in private
environment variables; `config.yml` contains framework and infrastructure setup.

Read `ai.model/global` using `/settings ai.model global`. Its initial live mode
is OpenRouter with `openai/gpt-4.1-mini`, price ceilings of $0.40 input and $1.60
output per million tokens, four requests per mission and a $0.25 daily budget.
These are editable initial records. Requests reserve the maximum estimated
cost before contacting the provider. An ambiguous request keeps its reservation
and is not automatically repeated. Provider data collection is denied by default.

```bash
docker compose --env-file .env.runtime exec -T api python -m src.cli.live_check --paid-model-smoke
```

This performs a real, budgeted model request, persists its smoke mission and
cost, and checks current database configuration, bot identities and all three
live market quotes. A successful check is required before claiming the model
works. It does not send a channel post.

Channel publication initially uses `PORTAL_DRY_RUN=true` and has no destination.
Update the complete `portal.policy/global` record with a negative channel ID,
then set the private environment's dry-run flag to `false` and recreate API,
worker and scheduler. The shared daily cap and quiet hours still apply.

## Verification

```bash
.venv/bin/ruff check api bots packages tests tools
.venv/bin/ruff format --check api bots packages tests tools
.venv/bin/pyright
.venv/bin/python -m pytest tests -q
.venv/bin/python tools/check_compose.py
```

Native integration tests require `PORTAL_TEST_DATABASE_URL` with permission to
create isolated MySQL test databases and `PORTAL_TEST_REDIS_URL`. Set
`PORTAL_TRANSPORT_TESTS=1` to exercise the native MCP stdio transport. The CI job
provides these services, checks migration drift, and runs actual scheduler and
worker processes. Telegram is a controlled external boundary in those tests.
Tests without these variables skip the corresponding infrastructure workflows.

See [architecture](docs/architecture.md), [configuration](docs/configuration.md),
[deployment](docs/deployment.md), [security](SECURITY.md) and
[requirements and review](docs/review.md). License: [MIT](LICENSE).
