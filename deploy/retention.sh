#!/usr/bin/env bash
set -euo pipefail
root_directory=${PORTAL_DEPLOY_ROOT:-/opt/portal}
script_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
test "$(id -u)" -eq 0
command -v systemctl >/dev/null
install -d -m 700 "$root_directory/maintenance"
install -m 700 "$script_directory/retention_host.py" "$root_directory/maintenance/retention.py"
install -d -m 755 /etc/systemd/journald@portal.conf.d
cat > /etc/systemd/journald@portal.conf.d/retention.conf <<'CONFIG'
[Journal]
Storage=persistent
SystemMaxUse=64M
SystemMaxFileSize=1M
MaxFileSec=1min
MaxRetentionSec=23h58min
ForwardToSyslog=no
ForwardToKMsg=no
ForwardToConsole=no
CONFIG
systemctl add-wants sockets.target systemd-journald@portal.socket
systemctl start systemd-journald@portal.socket
systemctl restart systemd-journald@portal.service
if systemctl cat portal-backup.timer >/dev/null 2>&1; then
    systemctl disable --now portal-backup.timer
fi
if systemctl cat portal-backup.service >/dev/null 2>&1; then
    systemctl stop portal-backup.service
fi
cat > /etc/systemd/system/portal-retention.service <<UNIT
[Unit]
Description=Remove expired portal backups and journal history
Requires=systemd-journald@portal.socket
After=systemd-journald@portal.socket
[Service]
Type=oneshot
LogNamespace=portal
ExecStart=/usr/bin/python3 $root_directory/maintenance/retention.py $root_directory
UNIT
cat > /etc/systemd/system/portal-retention.timer <<'UNIT'
[Unit]
Description=Enforce the portal's rolling 24-hour file retention
[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=1s
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now portal-retention.timer
