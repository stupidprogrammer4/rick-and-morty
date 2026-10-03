# Requirements, structure, performance and security review

This review distinguishes implemented controls from execution evidence. It does
not establish production readiness, capacity or a complete penetration test.

## Implemented requirements

| Requirement | Owner and implementation |
| --- | --- |
| Separate API and bots | Papilio/Papilio Tasks API; aiogram webhook gateway |
| Auryx structure | Typed entities/DTOs, explicit interfaces/providers, one-repository CRUD services, coordinating commands and composite readers |
| MySQL | Native MySQL provider, aiomysql driver and static forward Alembic migration |
| Editable business behavior | Definition/value and source/config DB records with revisions; request-scoped reads |
| Rick/Morty voices | Database system prompts/templates and reaction/typing actions |
| Styled channel posts | Escaped HTML and database emoji-rich per-category styles |
| News | Hacker News source, article reading and mission-bound draft evidence |
| Prices | Three Talamala mappings, Decimal units, freshness and linked snapshots |
| Controlled publication | Human revision approval, shared quota/quiet hours, persistent pause and unknown-delivery resolution |
| OpenRouter | Live mode, bounded tools/output, provider ceilings and persisted cost reservations |
| Public source preparation | English docs, MIT, private-file exclusions and publication checks |
| Deployment preparation | Compose, CI/CD, digest releases, pinned SSH, backup and TLS template |

## Corrections made during review

| Finding | Correction and verification boundary |
| --- | --- |
| Business configuration in YAML | Converted to database records; seed schema and preservation tests |
| MySQL repeatable-read snapshots could miss duplicate/quota changes | Current locking reads under owner/publishing guards; fresh ORM reloads; native concurrency tests supplied |
| Unlinked market drafts could bypass quote provenance | Persisted snapshot, owner/body hash and freshness revalidation at schedule/dispatch |
| Pending publications could flood the queue after quota exhaustion | Recovery enqueues only remaining daily slots and skips pause/quiet/full-cap states |
| Interrupted delivery could resend a message | Sending leases become unknown; owner-only explicit resolution; real-DB delivery tests supplied |
| Shared env file exposed unnecessary secrets to bots | Explicit per-service environment and separate internal DB network |
| Live diagnostic could bypass cost accounting | Smoke mission uses the ordinary model ledger and budget reservation |
| Dependency graph did not match shared contract pin | Aligned Pydantic with the resolved verification graph; CI reinstalls and runs pip check |
| Queue and budget visibility was missing | Declared queue status read model in the protected status endpoint |
| Long Unicode evidence could exceed MySQL TEXT checkpoint capacity | MySQL MEDIUMTEXT for checkpoint history; native round-trip regression supplied |
| Non-ASCII authentication headers raised TypeError | Compare encoded bytes; the native API regression requires a 401 response |

## Performance assessment

Admission and publication locks protect concrete owner/quota invariants. Network
and model work occurs after short claim/reservation transactions commit. Queue
indexes cover status, due times and owner/status; no public collection performs
an unbounded list operation. API and workers each have independent DB pools.

The initial worker has one process and eight concurrent tasks. Raising this
without measuring MySQL connections, HTTP connection limits and MCP memory can
overload a small shared VPS. MCP starts a native subprocess for a model step;
startup cost and process memory can dominate short chat latency. Reuse must
preserve request-scoped owner/mission context and native MCP lifecycle.

Configuration reads parse 14 small JSON records per request/task, and bot
presentation requires an API round trip. This favors immediate edit visibility
at the initial admin-only volume. Measure query latency before adding caching;
a cache would need revision-aware invalidation and bounded staleness.

News gathers a bounded number of sources/articles concurrently and limits
download/body sizes. A failed feed currently fails the collection, and redirects
are deliberately rejected. Sites requiring redirects or JavaScript extraction
may produce no usable evidence. Article quality and extraction must be checked
against actual selected publishers. There is no load-test evidence.

The global publishing guard serializes channel quota reservation. This fits the
initial one-post/day policy; it is not evidence for high-volume multi-channel
publishing. Redis uses AOF and no-eviction; monitor memory, pending entries and
result retention before increasing traffic. MySQL/source/checkpoint retention
needs an explicit policy and a future bounded cleanup workflow.

## Verification evidence and open gates

Locally, 49 tests passed and 8 infrastructure tests were skipped in the final
available sandbox run. Unit coverage includes configuration schemas, presentation,
safe formatting, HTML escaping, price normalization/freshness, routing, quiet
hours, SSRF/redirect/size guards and native API authorization. MySQL, Redis,
native worker/scheduler and MCP transport tests are supplied and configured in
CI, but have not passed in this environment. External Telegram is controlled in
integration tests; no model provider or live Telegram result is inferred from it.

The sandbox denies socket writes and outbound SSH. Local Docker daemon access
is also unavailable. Compose configuration validation succeeds. Framework app,
task discovery and offline SQL generation can be checked without these services.
Paid OpenRouter, actual Talamala timestamps, server resources/TLS, webhook
registration, public GitHub push and a successful production release require
actual execution evidence. A configured live model is not a successful model call.

Remaining acceptance gates:

- Run the native integration suite and dependency/secret audits on an unrestricted
  runner; inspect failures rather than reducing those gates.
- Confirm live prices and all three timestamp/currency contracts.
- Run the paid model smoke request and private Telegram mission/tool workflows.
- Obtain the target channel ID and verify both bots' actual permissions.
- Inspect the existing VPS ingress and available resources, then verify DNS/TLS,
  exact-commit deployment, webhooks and an approved channel publication.
- Prove an isolated backup restore and arrange encrypted off-server backups.
- Add measured alerts for queue age, unknown deliveries, reserved model budget,
  DB/Redis/storage pressure and application restart loops.

## Scope beyond current workflows

The earlier planning document also proposed weekly category slot rotation,
music attachments/queue curation, multi-step editing dialogs, conversation reset,
retention automation and richer progress reports. Current commands support text
music drafts, explicit timestamp scheduling and independent missions. Those
additional workflows are not implemented and must not be advertised as complete.
The existing VPN sales bot, purchases and plan prices remain outside this service.

The security controls and residual risks are documented in [SECURITY.md](../SECURITY.md).
