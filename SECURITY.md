# Security

## Exposure and credentials

Public Nginx ingress exposes only the two webhook routes and a minimal liveness
endpoint. API and bot internal routes bind to host loopback through Compose.
MySQL and Redis have no host ports and use an internal Docker network. The bot
container has no database credentials or model key. Python containers run as
an unprivileged user, drop capabilities and deny privilege escalation.

Every webhook has an independent secret compared in constant time. Only private
messages and callbacks from allowlisted administrator IDs reach command logic.
Callbacks retain the originating bot and draft revision. Internal service calls
use a long random bearer key and validate the owner where applicable.

Private environments, configuration, server credentials and backups are excluded
from Git and image contexts. CI scans committed history with redacted Gitleaks
output and audits resolved PyPI dependencies. Pinned custom framework archives
also require a source review; vulnerability databases do not establish their
safety. SSH validates a previously saved SHA256 host-key fingerprint.

## External content and model capabilities

Source HTTP permits configured HTTPS hosts on port 443, rejects URL credentials,
redirects, private/reserved IPs and mixed public/private DNS answers, and connects
through a resolver that returns only the validated public addresses. Response
sizes and timeouts are bounded. Proxy environment variables are not trusted.

External article text is untrusted evidence. Tools enforce typed arguments,
current mission ownership, status and deadline. The model receives no shell,
payment, plan pricing, service credential or channel publication tool. Only
collected evidence can create a news draft. Human review remains necessary for
accuracy and prompt injection: evidence IDs establish provenance, not truth.

Telegram HTML is escaped. Database templates reject unknown placeholders and
attribute access. Market publication requires persisted, complete fresh quotes
and an unchanged deterministic draft body. Model request costs and channel
delivery slots have separate transactional reservations.

## Operational controls and residual risks

- Protect Docker socket and server root access; either grants access to secrets.
- Keep encrypted off-server backups and perform an actual isolated restore.
  Local pre-migration dumps alone do not protect against loss of the VPS.
- Inspect TLS, DNS, ports, storage, available RAM and existing proxy services
  before installing ingress. The provided template must not replace another
  application's server block.
- Check OpenRouter privacy/provider terms, live credits and Telegram permissions.
  A denied provider data-collection request does not prove zero retention.
- Never automatically replay an `unknown` model request or message delivery.
  Resolve it using provider/Telegram evidence or an explicit owner decision.
- Logs intentionally avoid raw provider bodies, credentials and HTTP access
  URLs. Review new logging integrations before enabling request tracing.
- There is no public-user access, payment integration, high availability,
  guaranteed source accuracy or demonstrated production penetration test.

## Reporting a vulnerability

Contact the repository owner privately through their GitHub profile. Include
affected commit, reproduction steps and impact without posting live credentials
or private chat/article data in public issues.
