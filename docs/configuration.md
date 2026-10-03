# Database configuration

## Records

| Key | Scopes | Validated record |
| --- | --- | --- |
| `portal.policy` | `global` | Channel, time zone, quiet hours, quotas and deadlines |
| `ai.model` | `global` | Mode, model, price ceilings, token/tool/reaction limits and budget |
| `market.policy` | `global` | Backend, enabled flag, allowed hosts and quote freshness |
| `market.engine` | `global` | Source timeouts, scheduler defaults, aggregation, outliers and cache age |
| `automation.policy` | `global` | Owner, enabled rules, anchored intervals, topics and prompts |
| `presentation` | `global` | Reactions, labels, item emojis and post length |
| `voice` | `rick`, `morty` | System prompt and persona response templates |
| `post.style` | `news`, `tech`, `market`, `music`, `notice` | Publisher identity, heading, separators, footer and hashtags |
| `market.quote` | `gold`, `usd`, `silver` | Endpoint, JSON paths, currency, basis, purity and labels |

The seed contains 9 definitions, 16 scoped values and Hacker News sources.
Values use validated JSON text, optimistic revision numbers and a unique
definition/scope key. Voice templates permit only documented placeholders;
Python attribute access and formatting expressions are rejected. Business
settings never fall back to a fabricated value if required records are missing.

## Editing

The private commands `/settings key scope` and `/set_setting key scope JSON`
read and update complete records. The second command obtains the current
revision and submits a validated change. `/prompt text` edits only the
receiving persona's system prompt while preserving its response templates.

The API exposes definition, value, schema, bot presentation and paginated source
operations under `/internal/configuration`. Every route requires the private
service bearer key and an allowlisted `X-Portal-Owner`. Source creation coordinates
the definition and its configuration in one transaction. Definition and source
configuration revisions have separate ownership.

Edit a record by first reading it, modifying its JSON, and writing its current
revision. A conflicting revision returns an error; refresh before retrying.
Credentials must never be stored in presentation records or source URLs.

## Source setup

The enabled initial news source uses the official Hacker News RSS feed.
The alternative Algolia search source is seeded disabled.
The database stores its endpoint, topics, default topics, result size and
allowed hosts. External article fetching permits public HTTPS destinations and
checks resolved IPs even when Hacker News links to a different host. XML parsing
rejects DTDs and external entities. Direct
`/summarize` URLs must belong to an enabled source's host allowlist.

The initial Talamala endpoint mappings come from the Auryx integration:

- `https://api.talamala.ir/api/assets/gold18/price`
- `https://api.talamala.ir/api/assets/usd/price`
- `https://api.talamala.ir/api/assets/silver999/price`

The expected paths are `data.price` and `data.priced_at`. The initial records
describe rial values, gold per gram at purity 750, silver per gram at purity 999
and one US dollar. Validate the live contract before relying on these records.
Missing or naive quote timestamps are rejected. An authenticated provider can
use the private `TALAMALA_API_TOKEN` environment variable; it is only sent to
configured, validated endpoints.

## Model setup

`ai.model/global` selects disabled, fake or OpenRouter mode. Fake mode is
accepted only with transport dry-run enabled, and synthetic drafts cannot be
published live. OpenRouter mode requires a nonempty model and known input/output
cost ceilings. Model rates and limits are stored in the database.

The initial model is [GPT-4.1 Mini on OpenRouter](https://openrouter.ai/openai/gpt-4.1-mini).
The request uses tool support when required, bounded output, no automatic HTTP
retry and [provider price ceilings](https://openrouter.ai/docs/guides/routing/provider-selection).
Unsupported required parameters or providers above the ceiling cause a failure.
API credentials remain in the private runtime environment.

## Recurring publication

`automation.policy/global` owns the allowlisted administrator and independent news
and price rules. Each rule has `enabled`, `interval_seconds`, an aware `starts_at`,
`topic`, `lookback_seconds` and `prompt`. Set the news interval to 18000 seconds
and prices to 3600 seconds for five-hourly Rick summaries and hourly market reports.
Seeds leave both rules disabled. Configure an owner and channel before enabling.

Slots remain anchored across restarts. After downtime only the latest slot is
admitted, with a unique mission key preventing duplicates. Explicitly enabled rules
authorize their own drafts through the ordinary publication workflow; manual drafts
still require approval. Pause, daily quota and quiet hours apply to both. A cap of
30 accommodates this cadence; equal quiet boundaries disable the quiet window.
Source failure, absent evidence or invalid quotes prevents publication.

`post.style/news` and `post.style/market` own category hashtags. The presentation
record's `asset_styles` maps each asset to its own emoji and hashtag.

## Auryx market engine

`market.policy.backend` selects `talamala` or `auryx`. The Auryx port includes
assets, symbols, source adapters, aggregation/outliers, purity/unit/FX conversions,
bubbles, supplier login adapters, candles, ticker history and statistics. Store
product pricing is outside this application. Persistence uses native Papilio MySQL
and background work uses native Papilio Tasks Redis. Sources and engine defaults
live in database records; the idempotent pricing seed preserves edited records and
creates 18 disabled sources, three assets, six symbols and a bubble.

Protected `/internal/pricing` routes expose CRUD, paging, source readings, conversion
and charts. Supplier prices enter through the protected supplier-price endpoint
and native queue, replacing Auryx's Rabbit adapter. No Auryx credentials are copied.
Configure source endpoints, allowed hosts, parser parameters and credentials before
enabling them. Invalid public-IP checks, redirects and excessive responses fail closed.

TGJU source timestamps are preserved; adapters lacking them mark receipt time
instead. Re-fetching an unchanged rate does not refresh its original timestamp.
`market.engine.max_quote_age_seconds` and `market.policy.max_age_seconds` bound age
up to 24 hours. Reports accepting latest declared rates display original times.
Wallex's USDT/toman pair must not be presented as USD. Every required asset must
have an accepted positive quote before a market report can be published.
