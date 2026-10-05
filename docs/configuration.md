# Database configuration

## Records

| Key | Scopes | Validated record |
| --- | --- | --- |
| `portal.policy` | `global` | Channel, time zone, quiet hours, quotas and deadlines |
| `ai.model` | `global` | Mode, model, price ceilings, token/tool/reaction limits and budget |
| `market.policy` | `global` | Backend, report mode, instruments, freshness and asset charts |
| `market.engine` | `global` | Source timeouts, scheduler defaults, aggregation, outliers and cache age |
| `automation.policy` | `global` | Owner, enabled rules, anchored intervals, topics and prompts |
| `occasions.policy` | `global` | Daily Rick calendar schedule, categories, custom events and exclusions |
| `presentation` | `global` | Reactions, labels, item emojis, pagination and post length |
| `voice` | `rick`, `morty` | System prompt and persona response templates |
| `post.style` | `news`, `tech`, `market`, `charts`, `occasions`, `music`, `notice` | Publisher identity, heading, separators, footer and hashtags |
| `market.quote` | `gold`, `usd`, `silver` | Endpoint, JSON paths, currency, basis, purity and labels |

The seed contains typed setting definitions, scoped values and Hacker News sources.
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

`automation.policy/global` owns the allowlisted administrator and independent news,
price and chart rules. Each rule has `enabled`, `interval_seconds`, an aware `starts_at`,
`topic`, `lookback_seconds`, `prompt` and optional `system_prompt`. The requested cadence uses prices every
7200 seconds, standalone charts every 25200 seconds and news every 10800 seconds,
anchored at 10:00 Tehran time. Intervals continue across midnight. Seeds leave
all rules disabled. Configure an owner and channel before enabling.

After running the idempotent seed, `python -m src.cli.content_schedule` applies
this cadence atomically to the existing database records, enables market charts
and daily occasions, selects the existing schedule owner or an allowlisted
administrator, and retains prompts, sources, exclusions and the channel. It sets
the timezone to `Asia/Tehran`, disables quiet hours and raises the daily cap to
at least 30. Use `--owner-id` to select a specific allowlisted administrator.

Slots remain anchored across restarts. After downtime only the latest slot is
admitted, with a unique mission key preventing duplicates. Explicitly enabled rules
authorize their own drafts through the ordinary publication workflow; manual drafts
still require approval. Pause, daily quota and quiet hours apply to all schedules. A cap of
30 accommodates this cadence; equal quiet boundaries disable the quiet window.
Absent evidence or invalid required quotes prevents publication. Source reports
retain the other accepted providers when one source fails.

News uses its dedicated `automation.policy.news.system_prompt` plus a separate
news-reading task in `news.prompt`, for both manual and scheduled missions.
The agent reads collected article evidence and writes the facts and its reaction
together, with evidence-backed excitement or criticism. Article IDs remain linked
internally; source links and persona labels are excluded from channel text.
`python -m src.cli.rick_voice` updates the existing news and general Rick prompts,
clears the news wrapper, cancels queued news in the old format, and applies prices
every 7200 seconds and charts every 25200 seconds while preserving anchors,
enabled flags and the remaining settings.

`post.style/news`, `post.style/market` and `post.style/charts` own category hashtags.
When the standalone chart rule is enabled, price reports do not attach charts;
the chart rule produces its own parent post and line/candlestick images. The presentation
record's `asset_styles` maps each asset to its own emoji and hashtag.

## Daily occasions

Run the idempotent seed after upgrading to add `occasions.policy/global`.
Read it using `/settings occasions.policy global`. Set `owner_id` to an
allowlisted administrator and `enabled` to `true`. `time: "10:00:00"` controls
preparation, while `publish_start: "15:00:00"` and `publish_end: "18:00:00"`
bound random publication; save the complete record with `/set_setting`. The schedule
uses `portal.policy.timezone`, initially `Asia/Tehran`. Configure the channel,
live model and delivery mode as usual. The existing shared daily post cap
must accommodate occasions alongside other enabled schedules.

The scheduler admits at most one occasions mission per local date. Restarting
between preparation and the publication deadline admits today's slot; it does not
replay previous days or admit a missed slot after 18:00. The random delivery time
is chosen once, stored with the publication and retained after restarts. Late
preparation chooses only a remaining time within the window.
Rick's agent uses the dedicated `occasions.policy.system_prompt`, followed by
its separate task `prompt`, and reads `get_calendar_occasions` before calling
`create_occasion_draft`. The public post contains selected titles and commentary.
Sources, regional notes and coverage warnings stay in internal tool evidence;
source links, persona announcements and calendar status labels are rejected in
draft text. `post.style/occasions` starts with empty heading, footer and hashtags
so the channel receives the character's words without a portal notice wrapper.
An empty selection admits no scheduled mission or post. Manual requests retain
the ordinary approval flow.

The default `selection: "youth"` uses an explicit curated list of informal,
relationship, internet, music, science, health and cultural occasions.
`max_events: 3` caps daily output (valid range 1–5). Administrative and government
observances are excluded. `selection: "all"` is available for explicit catalogue
inspection and date-engine checks. After seeding a new release,
`python -m src.cli.occasion_voice` updates the live persona, task prompt and youth
selection, preserves timing, owner and custom entries, and cancels old queued
occasion posts. Seeding alone preserves existing policy edits.

`types` selects `Informal`, `Iran`, `AncientIran`, `International`, `Afghanistan`,
or `IranFormer`. Informal occasions come first by default, followed by Iranian,
ancient Iranian and international records. They include social, relationship
and internet observances. Status and provenance remain internal. The youth
selection announces only curated records. `excluded_ids` suppresses
specific records. `custom_events` adds entries with a unique `id`, `title`,
`calendar` (`Persian`, `Gregorian`, `Hijri`), `month`, `day`, optional `year`,
`holiday`, and `source`. Without `year`, an event recurs in its own calendar.
For example, an annual personal event can use
`{"id":"portal-day","title":"Portal anniversary","calendar":"Persian","month":7,"day":13,"source":"Personal calendar"}`.

Packaged sources cover the recorded Iranian, ancient and international events,
including movable calendar rules. Lunar dates use documented Iranian month
starts, with explicit warnings outside known coverage. These records are a
versioned catalogue, not an exhaustive registry of every worldwide informal
event. Refresh the packaged datasets when new annual calendars are released;
their provenance files record sources, pinned revisions and coverage.

## Auryx market engine

`market.policy.backend` selects `talamala` or `auryx`. The Auryx port includes
assets, symbols, source adapters, aggregation/outliers, purity/unit/FX conversions,
bubbles, supplier login adapters, candles, ticker history and statistics. Store
product pricing is outside this application. Persistence uses native Papilio MySQL
and background work uses native Papilio Tasks Redis. Sources and engine defaults
live in database records; the idempotent pricing seed preserves edited records and
creates 18 disabled sources, four assets, seven symbols and a bubble.

Protected `/internal/pricing` routes expose CRUD, paging, source readings, conversion
and charts. Supplier prices enter through the protected supplier-price endpoint
and native queue, replacing Auryx's Rabbit adapter. No Auryx credentials are copied.
Configure source endpoints, allowed hosts, parser parameters and credentials before
enabling them. Invalid public-IP checks, redirects and excessive responses fail closed.

TGJU source timestamps are preserved; adapters lacking them mark receipt time
instead. Re-fetching an unchanged rate does not refresh its original timestamp.
`market.engine.max_quote_age_seconds` and `market.policy.max_age_seconds` bound age
up to 24 hours. Reports accepting latest declared rates display original times.
Wallex has its own `usdt` asset and `usdt_rial` symbol; it never enters USD aggregation.

`market.policy.report_mode` selects `aggregate` or `sources`. Aggregate reports
require the original three assets. Source reports publish every accepted reading
from active providers, grouped by the configured `instruments` mapping (native
symbol to label, asset, basis, purity and market). They retain each provider's
buy/sell rates, name, URL and source or receipt timestamp. Global ounces remain in
USD, separately from local grams. Invalid, closed, expired, future or outlier rates
are excluded; a failing provider does not hide the others. Empty reports fail.
Source-report outliers use the editable engine threshold per native instrument.

`presentation` owns buy/sell/unit labels and source emoji, including the independent
USDT emoji and hashtag. Source credentials and enabled state remain in native
pricing records. A successful HTTP response alone does not establish rate accuracy;
verify the provider's units and parser contract before enabling it.

## Price pages and asset charts

Enable `presentation.market_pagination_enabled` for source reports. Each page
contains one instrument and at most `market_sources_per_page` providers (default
four). `previous_page_label`, `next_page_label` and `page_label` control the inline
buttons; the counter accepts `{page}` and `{total}`. Buy/sell emojis, labels,
asset emojis, hashtags, headings, separators and footers remain database settings.
Pages are frozen when scheduling: navigating an older report preserves its rates
and timestamps. The private draft previews page one with a page counter; the
associated immutable source snapshot retains every accepted reading, even when
the complete report exceeds one Telegram message. The bot verifies the report,
bot role, channel and message ID
before editing it. Administrative callbacks still require a private admin chat.

Enable `market.policy.charts.enabled` to send one image per native calculated
asset after the parent price report is confirmed sent. `window` accepts `daily`,
`weekly` or `monthly`. Dimensions, background/foreground/up/down colors, captions,
plot labels and per-asset `asset_labels`/`asset_symbols` are editable in this record.
Seeded chart titles use English for reliable rendering; Telegram captions use the
asset title and emoji/hashtag configured in the database.

Charts use closed candles from the native calculated-asset history. Their line
shows the same candles' close values; OHLC shows open/high/low/close. Values are
converted from rial to toman. Missing periods remain gaps, and assets without
history display an empty chart. Enable the asset's native calculation schedule
to accumulate observations; new assets cannot supply historical prices from
before collection began. These candles describe calculated rates, not trades.

Rendering runs in a worker thread, outside database transactions and the event
loop. Images are bounded to 256 KiB and sent as PNG bytes, without external image
hosting. Four child deliveries count as part of their parent report, rather than
four extra reports against the daily report quota. Photo statuses are exposed at
`GET /internal/publications/{id}/charts`; ambiguous sends require an explicit
owner decision at `POST /internal/publications/charts/{id}/resolve` with either
`message_id` or `resend: true`. Automatic recovery never repeats an unknown send.
