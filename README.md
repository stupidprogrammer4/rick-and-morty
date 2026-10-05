# Rick and Morty Portal

Two Persian Telegram assistants for private administration, sourced news,
verified market reports and scheduled channel posts. Rick is sarcastic and
analytical; Morty is nervous, friendly and practical. Their system prompts,
responses, reactions and channel presentation are editable database records.

Price reports support inline page navigation, asset-specific emojis and tags,
linked providers and separate buy/sell rates. Each calculated asset can include
a PNG with its closing-price line and OHLC history alongside the hourly report.

AMU Downloader is a separate public bot for private media downloads. Its welcome
image, emoji menu, progress cards and paginated history accompany downloads from
Instagram, YouTube, SoundCloud, Spotify and other supported public sources.

## Components

| Directory | Responsibility |
| --- | --- |
| `api` | Papilio API, domain workflows, MySQL persistence and Papilio Tasks |
| `bots` | aiogram webhooks, private admin commands and Telegram delivery |
| `packages/contracts` | Typed contracts shared by both applications |
| `deploy` | Compose release, backups and restricted Nginx ingress |

API features are grouped under `api/src/modules`:

| Group | Modules |
| --- | --- |
| `ops` | Database settings, guards, status and task history retention |
| `automation` | Missions and bounded agents |
| `content` | News evidence, drafts, publications and private replies |
| `pricing` | Market sources, assets, calculations, history, charts and reports |
| `media` | Download workflows, source extraction, delivery and storage |

Media source inputs are separate from persisted download jobs. Completed files
enter the delivery queue immediately; download workflows retain their positions
for ordered delivery. Media workers use their own Papilio Tasks application.
Historical task names remain registered for queued work across upgrades.

MySQL owns configuration, missions, collected evidence, drafts, approvals,
publication reservations and model costs. Redis carries native Papilio Tasks.
The model can read permitted evidence and create drafts. Channel publication
requires human approval for manual drafts. Explicitly enabled database rules
authorize recurring news and price drafts through the same publication workflow.

## Start locally

Requirements: Python 3.13, Docker with Compose v2, two distinct Telegram bot
tokens, an OpenRouter key and numeric administrator IDs.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r api/requirements-dev.lock -r bots/requirements.lock
.venv/bin/python -m pip install --no-deps -e packages/contracts -e api -e bots
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

## Configuration and OpenRouter

Business configuration is stored in MySQL using separate setting definitions
and scoped values, plus news and market sources and their configurations. The
initial `api/seeds/defaults.json` creates missing records; restarting or seeding never
overwrites administrator changes. Credentials and transport belong in private
environment variables; `config.yml` contains framework and infrastructure setup.

Read `ai.model/global` using `/settings ai.model global`. Its initial live mode
is OpenRouter with `openai/gpt-4.1-mini`, price ceilings of $0.40 input and $1.60
output per million tokens, four requests per mission and a $0.25 daily budget.
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

## Public media downloader

Set `MEDIA_DOWNLOADER_TG_BOT` and an independent
`PORTAL_MEDIA_WEBHOOK_SECRET`, then expose `/telegram/media` through HTTPS.
Start the downloader with `/start`; send a public HTTPS link or use its menu.
`/audio URL` requests audio. `/jobs`, `/status ID` and `/cancel ID` operate only
on the requesting user's private downloads.

Instagram posts include all discovered carousel slides, in order. YouTube and
SoundCloud collections download concurrently and retain their original numbers
for ordered delivery; collections exceeding the
configured limit are rejected rather than silently truncated. Spotify supplies
track metadata and searches for matching public audio from another source; the
file caption identifies its actual source. Matching checks the track title,
artist, version and full duration; a preview is not a successful download.
Optional Spotify API credentials provide catalog metadata where permitted.
Playlist API access requires an authorized user token in private
`PORTAL_SPOTIFY_ACCESS_TOKEN`; client credentials only enable track and album
catalog requests. The public bot rejects private playlists even with a token.
Public embeds and API permissions do not guarantee access to a complete playlist;
incomplete collections are rejected rather than partially reported as complete.
Login-only sources need an authorized cookie file; DRM and live streams are
unsupported. Extraction can also fail because a source blocks the server.

The database record `media.policy/global` owns quotas, enabled providers, size
and duration limits, download concurrency, source timeouts/retries, extractor
request intervals, HTTP user agent, disk reserves and
the welcome/menu presentation. Read or
update it through the administrator's existing settings commands. Credentials,
cookie paths and the shared volume remain private infrastructure configuration.

Database source routes choose the ordered extraction methods. Direct files and
supported Instagram/Pinterest metadata use asynchronous HTTP; file bodies stream
into bounded temporary storage without starting a Python process per file.
An optional `media.policy/global.youtube_api_url` selects a public Cobalt-compatible
API for complete YouTube MP3/M4A or MP4 files. Its endpoint is stored in MySQL,
not in source code. Single-video planning avoids SDK metadata requests when it is
configured; failed API resolution falls back to the bounded metadata SDK.
Returned file URLs still pass public-network checks, size limits and actual file
validation. The API is an external dependency; its availability is not guaranteed.
YouTube collection metadata and music searches use bounded AnyIO threads. Spotify catalog
requests and compatible MP3/M4A or muxed MP4 downloads use asynchronous HTTP;
Mutagen validates duration and writes audio tags in those same bounded threads.
SoundCloud MP3 HLS segments stream concurrently into bounded temporary files and
are joined in their original order in a bounded thread, without transcoding.
Encrypted, live and unsupported segmented formats are rejected.
These YouTube and Spotify transfers do not start codec or Python child processes.
They reject sources that only expose formats requiring conversion or merging.
Other SDK and browser fallbacks retain isolated processes, and their codec
conversion retains time and output-size limits. The video resolution limit
applies to the shorter edge, including portrait videos.

`media.policy/global` also controls YouTube client selection, music search
sources, matching limits and the lifetime of successful Telegram file references.
File references are stored in MySQL, isolated by bot and media options, and reused
without retaining media on disk. An expired Telegram reference triggers a fresh
download; uncertain sends are never automatically repeated.

Optional private `PORTAL_YOUTUBE_TOKEN_PROVIDER_URL` connects to an existing
HTTP PO token provider through its `/get_pot` endpoint.
`PORTAL_YOUTUBE_PROXY_URL` configures an existing YouTube metadata proxy.
Neither setting starts another service. Source login challenges and unavailable
direct formats can still prevent downloads, even when metadata extraction works.

Planning, downloading and ordered Telegram delivery have separate application
owners and native tasks. Collection downloads use `asyncio.gather`; each completed
file immediately dispatches its delivery work, while original item numbers control
sending order. Database writes finish before network work begins. Independent item
leases and workspaces isolate failures. Normal progress dispatches immediately;
recovery only handles interrupted work. Temporary files are removed after every
delivered item; scheduled cleanup removes aged inactive job directories.
Uncertain Telegram deliveries are recorded and never automatically resent.

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
