# Rick and Morty Portal

Two Persian Telegram assistants for private administration, sourced news,
verified market reports and scheduled channel posts. Rick is sarcastic and
analytical; Morty is nervous, friendly and practical. Their system prompts,
responses, reactions and channel presentation are editable database records.

Price reports support inline page navigation, asset-specific emojis and tags,
linked providers and separate buy/sell rates. Each calculated asset can include
a PNG with its closing-price line and OHLC history alongside the hourly report.

## Components

| Directory | Responsibility |
| --- | --- |
| `api` | Papilio API, domain workflows, MySQL persistence and Papilio Tasks |
| `bots` | aiogram webhooks, private admin commands and Telegram delivery |
| `packages/contracts` | Typed contracts shared by both applications |
| `packages/calendar` | Shared date calculations and sourced occasion catalogue |
| `deploy` | Compose release, file/log retention and restricted Nginx ingress |

API features are grouped under `api/src/modules`:

| Group | Modules |
| --- | --- |
| `ops` | Database settings, guards, status and task history retention |
| `automation` | Missions and bounded agents |
| `content` | News evidence, drafts, publications and private replies |
| `pricing` | Market sources, assets, calculations, history, charts and reports |

MySQL owns configuration, missions, collected evidence, drafts, approvals,
publication reservations and model costs. Redis carries native Papilio Tasks.
The model can read permitted evidence and create drafts. Channel publication
requires human approval for manual drafts. Explicitly enabled database rules
authorize recurring news and price drafts through the same publication workflow.

## Start locally

Requirements: Python 3.13, Docker with Compose v2, two distinct Telegram bot
tokens, a Groq key and numeric administrator IDs.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r api/requirements-dev.lock -r bots/requirements.lock
.venv/bin/python -m pip install --no-deps -e packages/contracts -e packages/calendar -e api -e bots
.venv/bin/python -m pip check
cp .env.example .env.runtime
cp config.yml.sample config.yml
# Fill bot/model credentials, administrator IDs, independent secrets and DB DSN.
# Match the private config.yml database DSN to PORTAL_DATABASE_URL.
docker compose --env-file .env.runtime up -d --build
```

Keep both private files out of Git. Compose runs a forward Alembic migration and
an idempotent seed before starting the API, worker, scheduler and bots.

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
| `/prices` | Fetch accepted market rates and prepare a source or aggregate report |
| `/occasions [YYYY-MM-DD]` | Rick drafts the configured calendar occasions for today or a Gregorian date |
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
administrative command is restricted to allowlisted administrators in private
chats. Channel readers can use price-page buttons; those buttons can only edit
the matching published report.

## Configuration and Groq

Business configuration is stored in MySQL using separate setting definitions
and scoped values, plus news and market sources and their configurations. The
initial `api/seeds/defaults.json` creates missing records; restarting or seeding never
overwrites administrator changes. Credentials and transport belong in private
environment variables; `config.yml` contains framework and infrastructure setup.

Recurring prices, charts and news have independent one-, three- and two-hour
intervals anchored at 10:00 Tehran time. After seeding,
`python -m src.cli.content_schedule` activates this cadence for an existing
channel and administrator, preserves content settings, disables quiet hours
and raises the daily cap to at least 45.

Daily occasions use `occasions.policy/global`. Rick prepares the draft at 10:00
and schedules delivery at a random time between 15:00 and 18:00 in the portal
timezone. The selected time persists across restarts. New installations seed
`selection: all` with every supported category. This includes every event present
in the configured Persian, Gregorian and Iranian lunar calendars, without the
three-event editorial limit. Optional `youth` selection, custom events and
explicit exclusions remain database policies. An empty day creates no post;
the packaged catalogue does not claim every observance worldwide.

`system_prompt` owns a dedicated Rick persona: science, individual freedom,
sharp satire of authority and bureaucracy, and natural conversational Persian.
`prompt` owns the drafting task. Rick stays in character without announcing his
persona. Calendar evidence remains internal; public posts contain event titles
and his commentary, without source links, calendar warnings or portal wrappers.
After seeding, `python -m src.cli.occasion_voice` applies these defaults to an
existing installation while retaining its owner, timings and custom events. It
also cancels queued occasion posts prepared with the previous format.

Private `/occasions` drafts require normal approval. The packaged calendar
provenance describes sources and coverage. Live model selection and tool routing
are database settings: `ai.model.tool_choice` supports `auto` for providers that
reject required-tool routing. Only validated evidence-backed drafts are published.
Zero local rate estimates reflect the account Free Plan; they do not control
provider billing. The account must stay on that plan.

Read `ai.model/global` using `/settings ai.model global`. Its initial live mode
is Groq with `qwen/qwen3.8-27b`, default non-thinking mode, zero local
Free Plan rate estimates, four requests per mission and a $0.25 daily budget.
These are editable initial records. Requests reserve the maximum estimated
cost before contacting the provider. An ambiguous request keeps its reservation
and is not automatically repeated. Provider data collection is denied by default.

Test live model behavior using a private `/ask rick` or `/ask morty` mission.
Inspect `/job` and `/status` for the persisted result and budget. `/prices` checks
the configured market backend without sending an unapproved channel post.

Channel publication initially uses `PORTAL_DRY_RUN=true` and has no destination.
Update the complete `portal.policy/global` record with a negative channel ID,
then set the private environment's dry-run flag to `false` and recreate API,
worker and scheduler. The shared daily cap and quiet hours still apply.

## Verification

```bash
.venv/bin/ruff check api bots packages tests
.venv/bin/ruff format --check api bots packages tests
.venv/bin/pyright
.venv/bin/python -m pytest tests -q
```

Native integration tests require `PORTAL_TEST_DATABASE_URL` with permission to
create isolated MySQL test databases and `PORTAL_TEST_REDIS_URL`. Set
`PORTAL_TRANSPORT_TESTS=1` to exercise the native MCP stdio transport. The CI job
provides these services, checks migration drift, and runs actual scheduler and
worker processes. Telegram is a controlled external boundary in those tests.
Tests without these variables skip the corresponding infrastructure workflows.

See [architecture](docs/architecture.md), [configuration](docs/configuration.md),
[deployment](docs/deployment.md), [security](SECURITY.md) and
[database schedules and prices](docs/configuration.md). License: [MIT](LICENSE).

### Occasion calendar

The API reads editable occasion definitions from MySQL. The shared
`packages/calendar` package calculates Gregorian, Persian and verified Iranian
lunar dates without network access. Its initial snapshot contains 894 records,
including UN, UNESCO and WHO observances and documented informal dates. Source
links, official status and topic tags accompany each record. Moving dates use
weekday rules; year-specific lunar observances are not repeated speculatively.
The coverage manifest distinguishes days from weeks. Iranian lunar coverage
currently ends on March 20, 2027 and reports missing coverage explicitly.

Authenticated `/internal/occasions` endpoints support paginated search, creation,
revision-checked edits and day lookup. Bootstrap adds missing records without
replacing edits or re-enabling disabled records. Calendar policies, exclusions
and publishing windows remain in MySQL. The upstream Persian-calendar snapshot
retains its packaged CC0 attribution and license.

Groq uses `qwen/qwen3.8-27b` with `GROQ_API_KEY` in the private `.env`.
Free use depends on the account Free Plan and its rate limits; no paid fallback
is configured. Enable ZDR in Groq Data Controls. Credit balance and aggregate cost
are not part of completion response bodies; missing cost stays unknown.

News generation bounds article excerpts sent to the model with the validated `ai.model.news_evidence_chars` setting (default 6,000 body characters across the selected articles). Full evidence remains stored, and shortened context is explicitly marked as truncated while retaining its source and evidence ID. This reduces oversized requests on free model tiers without dropping selected articles.
