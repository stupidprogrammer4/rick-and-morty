# Database configuration

## Records

| Key | Scopes | Validated record |
| --- | --- | --- |
| `portal.policy` | `global` | Channel, time zone, quiet hours, quotas and deadlines |
| `ai.model` | `global` | Mode, model, price ceilings, token/tool/reaction limits and budget |
| `market.policy` | `global` | Enabled flag, allowed hosts and quote freshness |
| `presentation` | `global` | Reactions, labels, item emojis and post length |
| `voice` | `rick`, `morty` | System prompt and persona response templates |
| `post.style` | `news`, `tech`, `market`, `music`, `notice` | Publisher identity, heading, separators, footer and hashtags |
| `market.quote` | `gold`, `usd`, `silver` | Endpoint, JSON paths, currency, basis, purity and labels |

The seed contains 7 definitions, 14 scoped values and one Hacker News source.
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

The initial news source uses the official [Hacker News search API](https://hn.algolia.com/api).
The database stores its endpoint, topics, default topics, result size and
allowed hosts. External article fetching permits public HTTPS destinations and
checks resolved IPs even when Hacker News links to a different host. Direct
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
