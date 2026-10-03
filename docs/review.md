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
| ORM bulk updates expired dirty attributes during async access | Match native repository behavior with `synchronize_session=False`; real MySQL workflows pass |
| MySQL rounded immediate delivery timestamps into the future | Preserve six fractional digits for due times with a forward migration; native delivery workflows pass |
| Dependency audit found outdated cryptography, JWT, dotenv and pip versions | Pin fixed releases; the runtime lock audit reports no known vulnerabilities |
| Live provider rejected an unadvertised parallel-tool parameter | Omit unsupported options and empty tool arrays; enforce the existing one-tool checkpoint limit; provider contract regression supplied |

## Performance assessment

Admission and publication locks protect concrete owner/quota invariants. Network
and model work occurs after short claim/reservation transactions commit. Queue
indexes cover status, due times and owner/status; no public collection performs
an unbounded list operation. API and workers each have independent DB pools.

The standalone worker has one process and eight concurrent tasks; the small
production server override reduces this to two concurrent tasks. Raising this
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

On 2026-10-03, the unrestricted local run passed all 57 tests, including
real MySQL migrations, native Redis scheduler/worker workflows and MCP stdio.
The regression suite also covers authorization, concurrency, unknown-delivery
resolution and a large Unicode checkpoint. External Telegram is controlled in
integration tests; those results do not prove live Telegram or model responses.
Both production images built from clean pinned dependencies and passed
`pip check` during construction. Runtime images remove pip and setuptools;
the image scanner found vulnerable vendored build-tool packages, which were
not needed to execute the application. Formatting and type checks also passed.

The VPS has 2 GiB RAM and existing services. Deployment uses an isolated portal
schema/user in its existing MySQL server, small independent connection pools,
a 64 MiB Redis limit and two worker tasks. Dedicated swap space covers
memory peaks. Native API startup measured approximately 126 MiB locally; this
is not a full worker/MCP load test. Existing TLS and ingress were inspected,
and the original service health route still responds after adding webhook paths.
Both real bot identities are distinct and have posting rights in the supplied
channel. All three Talamala endpoints returned HTTP 503 from the VPS; live
market validation remains unavailable and publication must fail closed.

Remaining acceptance gates:

- Complete dependency/secret audits and the exact-commit CI release checks.
- Confirm live prices and all three timestamp/currency contracts.
- Run the paid model smoke request and private Telegram mission/tool workflows.
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
