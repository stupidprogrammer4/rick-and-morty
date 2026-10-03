# Deployment at bot.amupouya.org

## Preflight

Run `python tools/check_server.py` in the installed development environment.
It reads the local Papilio Proxy environment for the host, user, password and
SHA256 key pin, and checks resources, Docker, listeners, Nginx and provider
reachability without changing services. It never publishes these credentials.

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
6. OpenRouter credits and provider policy allow the configured model. All three
   Talamala endpoints provide fresh, timezone-aware timestamps with the declared
   currency and basis.

## HTTPS ingress

`deploy/nginx.conf` is a complete host Nginx virtual-host template.
`deploy/nginx-locations.conf` supplies just the two webhook locations for an
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

To discover an existing shared channel, run `python tools/discover_channel.py`.
It inspects pending membership/channel updates without acknowledging them,
preserves active webhooks, and checks both bots' posting permissions. Telegram's
Bot API cannot enumerate all memberships; an older join may have no pending
event. `--write-policy` stores a uniquely verified channel in the running local
API's database policy. It never enables live delivery or sends a channel post.
When a public channel name is known, pass `--channel @username` to verify it directly.

The public repository contains only code, seeds and sample infrastructure.
Prepare private `.env.runtime` and `config.yml` locally. Keep dry-run enabled
while checking chat, evidence, market data and draft workflows.

Build/push API and bot images to GHCR with a full commit tag. Record immutable
digests in an images file:

```text
PORTAL_API_IMAGE=ghcr.io/owner/repository-api@sha256:<digest>
PORTAL_BOTS_IMAGE=ghcr.io/owner/repository-bots@sha256:<digest>
```

After ingress is provisioned, `tools/deploy.py --source /path/to/committed/repo
--images /path/to/images.env` uses pinned SSH, uploads a committed-source
archive and creates private server settings only if absent. Later deployments
preserve those settings. For private GHCR images, authenticate the server
separately using a restricted token; CI uses an ephemeral token directory.

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

Run the paid model smoke test once after deployment:

```bash
cd /opt/portal/current
docker compose -p portal --env-file .env.runtime exec -T api python -m src.cli.live_check --paid-model-smoke
```

Check the price provider separately with `python -m src.cli.live_check --market`
inside the API container. A temporary market outage does not stop webhook/chat
startup; market workflows still require valid fresh quotes. Include the server
override (`-f compose.yml -f compose.server.yml`) in Compose commands when it
is installed.

Then send `/ask rick` and `/ask morty` through Telegram, check `/job` and `/status`,
create/approve a draft and inspect a dry-run publication. Set the channel policy
in MySQL and disable transport dry-run only when its actual destination is known.
Verify a real approved publication and its persisted message ID.

## CI/CD

The GitHub workflow verifies formatting, types, publication contents, secrets,
dependencies, native MySQL/Redis/MCP/worker workflows, Compose and both images.
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
only after checking schema compatibility; otherwise restore a tested backup
with an explicit recovery decision. Release scripts retain previous source and
dumps but do not claim automatic rollback or a tested restore.
