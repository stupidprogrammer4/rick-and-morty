#!/usr/bin/env bash
set -euo pipefail
umask 077
root_directory=${PORTAL_DEPLOY_ROOT:-/opt/portal}
current_directory=$(readlink -f "$root_directory/current")
test -d "$current_directory"
mkdir -p "$root_directory/backups"
backup_file="$root_directory/backups/$(date -u +%Y%m%dT%H%M%SZ)-daily.sql.gz"
docker compose -p portal --project-directory "$current_directory" --env-file "$current_directory/.env.runtime" -f "$current_directory/compose.yml" exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --routines --triggers --events --databases portal' | gzip > "$backup_file"
test -s "$backup_file"
printf 'Backup created: %s\n' "$backup_file"
