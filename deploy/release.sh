#!/usr/bin/env bash
set -euo pipefail
umask 077

source_directory=${1:?Pass the uploaded release directory}
revision=${2:?Pass the full Git commit}
[[ "$revision" =~ ^[0-9a-f]{40}$ ]]
root_directory=${PORTAL_DEPLOY_ROOT:-/opt/portal}
test -f "$source_directory/portal-release.tar.gz"
test -f "$source_directory/portal-images.env"
test -f "$root_directory/private/.env.runtime"
test -f "$root_directory/private/config.yml"
command -v flock >/dev/null
docker compose version >/dev/null
exec 9>"$root_directory/.deploy.lock"
flock -w 120 9

release_directory="$root_directory/releases/$revision"
mkdir -p "$release_directory" "$root_directory/backups"
tar -xzf "$source_directory/portal-release.tar.gz" -C "$release_directory"
install -m 600 "$root_directory/private/.env.runtime" "$release_directory/.env.runtime"
# The private parent protects infrastructure settings on the host. The bind
# mounted file must also be readable by the non-root application UID.
install -m 600 "$root_directory/private/config.yml" "$release_directory/config.yml"
chown 10001:10001 "$release_directory/config.yml"
python3 - "$source_directory/portal-images.env" "$release_directory/.env.runtime" <<'PY'
import re
import sys
from pathlib import Path
images = Path(sys.argv[1]).read_text().splitlines()
if {line.partition('=')[0] for line in images} != {
    'PORTAL_API_IMAGE', 'PORTAL_BOTS_IMAGE',
} or len(images) != 2 or not all(re.fullmatch(
    r'PORTAL_(?:API|BOTS)_IMAGE=ghcr\.io/[a-z0-9/_.-]+@sha256:[0-9a-f]{64}',
    line,
) for line in images):
    raise SystemExit('Both images must use immutable registry digests')
with Path(sys.argv[2]).open('a') as stream:
    stream.write('\n' + '\n'.join(images) + '\n')
PY
compose=(docker compose -p portal --project-directory "$release_directory" --env-file "$release_directory/.env.runtime" -f "$release_directory/compose.yml")
shared_mysql=false
if test -f "$root_directory/private/compose.server.yml"; then
    shared_mysql=true
    install -m 600 "$root_directory/private/compose.server.yml" "$release_directory/compose.server.yml"
    compose+=(-f "$release_directory/compose.server.yml")
fi
"${compose[@]}" config --quiet
"${compose[@]}" pull
if "$shared_mysql"; then
    "${compose[@]}" up -d --wait --wait-timeout 180 redis
else
    "${compose[@]}" up -d --wait --wait-timeout 180 mysql redis
fi
# Keep the API and gateway alive until workers have drained their deliveries.
"${compose[@]}" stop scheduler
"${compose[@]}" stop media-scheduler
"${compose[@]}" stop media-worker
"${compose[@]}" stop worker
"${compose[@]}" stop bots
"${compose[@]}" stop api

# Preserve the current database before any forward migration.
backup_file="$root_directory/backups/$(date -u +%Y%m%dT%H%M%SZ)-$revision.sql.gz"
if "$shared_mysql"; then
    database_container=$(sed -n 's/^PORTAL_SHARED_MYSQL_CONTAINER=//p' "$release_directory/.env.runtime" | tail -n 1)
    [[ "$database_container" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]+$ ]]
    docker exec "$database_container" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --routines --triggers --events --databases portal' | gzip > "$backup_file"
else
    "${compose[@]}" exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --routines --triggers --events --databases portal' | gzip > "$backup_file"
fi
test -s "$backup_file"
"${compose[@]}" run --rm --no-deps migrate
"${compose[@]}" up -d --no-deps --wait --wait-timeout 180 api worker scheduler media-worker media-scheduler bots
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:18010/health/live >/dev/null
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:18011/health/live >/dev/null
python3 - "$release_directory/.env.runtime" <<'PYTHON'
import json
import sys
import urllib.request
from pathlib import Path
values = dict(line.split("=", 1) for line in Path(sys.argv[1]).read_text().splitlines()
              if line and not line.startswith("#") and "=" in line)
owner = min(int(value) for value in values["PORTAL_ADMIN_USER_IDS"].split(","))
request = urllib.request.Request("http://127.0.0.1:18010/internal/status", headers={
    "Authorization": "Bearer " + values["PORTAL_SERVICE_KEY"],
    "X-Portal-Owner": str(owner),
})
with urllib.request.urlopen(request, timeout=15) as response:
    result = json.load(response)
if not result["success"]:
    raise SystemExit("Database status gate failed")
print("Protected database status: reachable")
PYTHON
"${compose[@]}" run --rm --no-deps bots python -m portal_bots.webhooks
ln -sfn "$release_directory" "$root_directory/current.next"
mv -Tf "$root_directory/current.next" "$root_directory/current"
printf 'Release %s is healthy; webhooks registered. Database backup retained.\n' "$revision"
