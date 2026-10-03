# Portal requirements and accepted architecture

This document replaces the earlier Persian planning text with an English
requirements index. Telegram-facing prompts and content remain Persian.

## Accepted decisions

- Independent Rick and Morty Telegram identities and aiogram HTTPS webhooks.
- Papilio API and core, Papilio Tasks scheduling, MySQL persistence and Auryx
  application/infrastructure/presentation conventions.
- Rick/Morty-style system prompts, reactions and typing indications.
- Emoji-rich channel posts, Hacker News/API evidence and Talamala market quotes.
- Editable business settings in database definitions and scoped values, with
  separate source definitions/configurations; no business YAML configuration.
- Human approval of current draft revisions before channel publication.
- English repository documentation and commit messages, MIT license, public
  GitHub repository, CI/CD and deployment at bot.amupouya.org.
- Live OpenRouter activation and actual bounded paid testing.

## Workflow requirements

Private allowlisted admins can address either persona, create a team news
mission, summarize an allowed article, fetch prices, inspect/cancel missions,
review and approve/reject drafts, preview/confirm publication, schedule a
specific timestamp, pause publication and resolve an ambiguous Telegram send.
The model has only bounded read/evidence/draft/reaction tools and cannot publish,
run shell commands, make payments or change VPN plan pricing.

Quote handling preserves raw currency, unit/basis, purity and aware timestamps.
Rial-to-toman normalization uses Decimal exactly once. All three required quotes
must be valid and fresh; stale or fabricated market posts are rejected.

Both bot identities share channel quotas and quiet hours in the configured time
zone. Private responses return to the originating bot and do not consume channel
quota. Edits revoke approval; duplicate Telegram updates and publication requests
must be idempotent. Unknown paid requests and Telegram sends are retained for
explicit resolution rather than automatically retried.

## Implementation and acceptance

See [architecture](architecture.md) for ownership and transaction boundaries,
[configuration](configuration.md) for DB records, [deployment](deployment.md) for
release and recovery, and [review](review.md) for implemented requirements,
bottlenecks, actual verification evidence and unfinished acceptance gates.

The earlier plan's optional weekly slot rotation, curated music/media queue,
multi-step editor, conversation reset and retention automation are separate
future workflows. Existing VPN sales/proxy operations are outside this portal.
