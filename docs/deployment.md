# Deployment at bot.amupouya.org

## Preflight

Inspect server resources, Docker, listeners, ingress and source reachability.
Use the existing server access and verify its SSH host-key pin independently.

Verify all of the following before the first release:

1. DNS A/AAAA records reach this server. Remove an unusable AAAA record rather
   than claiming IPv6 works.
2. Existing ingress ownership, ports 80/443 and loopback ports 18010/18011 are
   known. The proxy application and its databases remain separate.
3. Docker Engine and Compose v2 are installed; the host can fetch pinned images
   and custom framework archives. TLS certificates renew reliably.
4. Available memory and disk can accommodate MySQL, Redis, API, worker, scheduler,
   bot gateway and per-mission MCP subprocesses. Measure actual peak usage.
5. Both tokens return distinct `getMe` identities; the administrator has started
   both private chats. Both bots have channel posting permissions.
6. OpenRouter credits and provider policy allow the configured model. Selected
   market sources provide correctly labeled quote times, currency and basis
   within the configured age policy.

## HTTPS ingress

`deploy/nginx.conf` is a complete host Nginx virtual-host template.
`deploy/nginx-locations.conf` supplies the webhook locations for an
existing TLS server block. Choose the form matching the inspected server.
Use a certificate covering `bot.amupouya.org`; the full template expects
`/etc/letsencrypt/live/bot.amupouya.org/`. Its HTTP challenge root is
`/var/www/portal-acme`. Obtain the certificate using the server's existing ACME
workflow, run `nginx -t`, then reload only the ingress service.

Do not install a second host Nginx if a container already owns ports 80/443.
Instead add the exact webhook locations to that ingress with an upstream that
can reach the loopback-bound gateway. Check the resulting network path and TLS
externally. No API or internal gateway path should become public.

## Initial release

Verify both bot identities and channel posting rights through Telegram before
configuring the negative channel ID in the database portal policy.

The public repository contains only code, seeds and sample infrastructure.
Prepare private `.env.runtime` and `config.yml` locally. Keep dry-run enabled
while checking chat, evidence, market data and draft workflows.

Build/push API and bot images to GHCR with a full commit tag. Record immutable
digests in an images file:

```text
PORTAL_API_IMAGE=ghcr.io/owner/repository/api@sha256:<digest>
PORTAL_BOTS_IMAGE=ghcr.io/owner/repository/bots@sha256:<digest>
```

Install private `.env.runtime` and `config.yml` under `/opt/portal/private` with
restricted access. Upload a committed-source archive named `portal-release.tar.gz`
and the digest file named `portal-images.env` into a temporary server directory.
Run `deploy/release.sh <temporary-directory> <full-commit>` from that archive.
Later releases preserve private settings. CI authenticates GHCR with an ephemeral
token directory and runs the same release script.

### Existing MySQL on a small server

`deploy/compose.server.yml` is an optional override for a server that already
runs MySQL. Provision a separate `portal` schema and a `portal` user with
privileges only on `portal.*`. Set `PORTAL_SHARED_MYSQL_NETWORK` and
`PORTAL_SHARED_MYSQL_CONTAINER` in the private runtime environment; the DSN
must resolve the existing server through that network. Install the override as
`/opt/portal/private/compose.server.yml`. Release and backup scripts detect it,
preserve the original databases and dump only the portal schema. Use small
connection pools in private infrastructure settings and verify memory limits.
The override requires Compose support for `!override` (verified with v2.40.3).

The release layout is `/opt/portal/private`, `/opt/portal/releases/<commit>`,
`/opt/portal/backups` and an atomic `/opt/portal/current` symlink. The release
script obtains a server lock, pulls digest-pinned images, checks Compose,
starts storage, dumps MySQL, drains/stops application workers, migrates, seeds,
starts applications, checks local liveness and database/gateway reachability,
and registers both webhooks. Database migration is a single forward operation before workers
resume. A failed gate exits with a nonzero status and does not advance `current`.

After deployment verify both webhook identities and protected database status.
Use ordinary private bot missions to check live model and market behavior.

Then send `/ask rick` and `/ask morty` through Telegram, check `/job` and `/status`,
create/approve a draft and inspect a dry-run publication. Set the channel policy
in MySQL and disable transport dry-run only when its actual destination is known.
Verify a real approved publication and its persisted message ID.

## CI/CD

The GitHub workflow verifies formatting, types, publication contents, secrets,
dependencies, native MySQL/Redis/MCP/worker workflows, Compose and both images.
Image builds validate dependencies before removing package managers and build
tools from the runtime filesystem. Webhook registration commands
run in separate temporary containers to preserve service memory headroom.
Main deployments run only after verification and push immutable GHCR images.
Full action commits are pinned and dependabot tracks action/package updates.

Configure these repository or production-environment secrets through `gh`:
`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PASSWORD`, `DEPLOY_HOST_KEY_SHA256`.
The saved host-key pin must be verified independently. Set secrets through
stdin, not command-line password arguments. No bot tokens are needed in CI;
production bot/model secrets remain on the server.

The deploy workflow assumes the initial private server settings and HTTPS ingress
already exist. It uses a temporary Docker credential directory, cleans that
credential on exit, and serializes releases. Deployment is not proven by the
presence of a workflow file: inspect the successful Actions run and the server
results for the exact commit.

## Backup and recovery

`deploy/backup.sh` creates a consistent gzip MySQL dump in the private backup
directory. Schedule it using the server's existing cron/timer, copy encrypted
backups off-server and define retention based on recovery requirements. Redis
uses AOF, but MySQL records remain authoritative; native recovery tasks requeue
eligible persisted work. Ambiguous deliveries must remain unresolved.

For recovery, stop writers and restore a verified dump into an isolated schema
first. Check migration revision, configuration, approvals, reservations and
unknown deliveries before replacing production state. Never automatically
downgrade a database after a failed deployment. A source/image rollback is safe
only after checking schema and persisted-data compatibility; otherwise restore a tested backup
with an explicit recovery decision. Release scripts retain previous source and
dumps but do not perform automatic rollback. Validate a restore independently
and maintain encrypted off-server copies with an explicit retention policy.

The source-report release adds USDT asset/symbol records and source snapshots.
It preserves existing records and needs no table change, but older images do not
understand those enum values or snapshot contracts. Treat recovery to an earlier
image as a data-compatibility decision, even when the Alembic revision is unchanged.

The chart release requires migrations through `20261003_chart_precision` before
API and workers start. It adds nullable frozen pages to publications and a
separate table for chart snapshots and delivery state; existing publication
rows are preserved.
Seeding leaves charts and pagination disabled on new installations and preserves
edited configuration on upgrades. Enable these settings explicitly after checking
native candle history, memory headroom and Telegram photo posting rights.

Check one parent report and each asset's recorded photo message ID after activation.
An interrupted renderer can be retried safely; an interrupted photo send becomes
unknown and needs an owner decision. The migration refuses a downgrade while
recorded pages or chart deliveries exist. Older images do not recover those child
deliveries; use compatible code or a verified backup with an explicit recovery
decision.
Chart schedules retain microseconds so immediately due sends are not rounded
into a future second by MySQL.

## Public media bot

The media release requires `20261004_media` before either media service starts.
It adds independent jobs/items tables and preserves existing settings, market
history, missions and publications. Downgrade refuses recorded download history.
The seed creates missing `media.policy/global` without overwriting edited values.

Install the updated shared-MySQL override when using an existing database.
`media-worker` and `media-scheduler` discover their native queues from the media
application; the ordinary mission worker does not execute downloads. Their
shared `media-data` volume is writable by UID 10001 and mounted read-only in
the bot gateway. The image includes FFmpeg and Chromium headless shell.
Allow for the browser's additional memory and image storage; only one download
executes at a time on the supplied small-server configuration.

Set the new bot token and its independent webhook secret in the private runtime
environment. Add the exact `/telegram/media` ingress, validate Nginx and reload
the existing service. Register webhooks with the normal release command. The
downloader is public in private chats; Rick/Morty administrative access stays
allowlisted. Users must start the downloader before it can send them files.

For sources requiring an authorized session, mount Netscape-format cookie files
read-only into the media worker and map provider names to their container paths
under `media.cookie_files` in the private configuration. Cookies must never enter
Git or images. Optional `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET` use the
free Spotify Web API for full collection metadata, not Spotify audio delivery.

Verify a complete small playlist, owned cancellation, persisted message IDs,
temporary-file deletion and container memory/restarts after activation. Known
Telegram rate limits wait before retry; ambiguous sends remain recorded without
automatic replay. A failed extraction may require a source session or a permitted
network path; installing a browser does not guarantee access to every service.
