import argparse
import base64
import hashlib
from pathlib import Path

import paramiko
from dotenv import dotenv_values


class PinnedHostKey(paramiko.MissingHostKeyPolicy):
    def __init__(self, expected: str):
        self.expected = expected

    def missing_host_key(self, client, hostname, key):
        fingerprint = "SHA256:" + base64.b64encode(
            hashlib.sha256(key.asbytes()).digest()
        ).decode().rstrip("=")
        if fingerprint != self.expected:
            raise RuntimeError("SSH host key does not match the saved pin")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path.home() / "w/Personal/papilio-proxy/.env",
    )
    args = parser.parse_args()
    values = dotenv_values(args.credentials)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(
        PinnedHostKey(str(values["SSH_HOST_KEY_SHA256"]))
    )
    checks = {
        "resources": "uname -m; free -m; df -h /; docker compose version",
        "containers": (
            'docker ps --format "{{.Names}} {{.Image}} {{.Status}} {{.Ports}}"'
        ),
        "ports": "ss -lntup",
        "tls_ingress": (
            "nginx -T 2>/dev/null | "
            "awk '/server_name|listen |proxy_pass|ssl_certificate / {print}'"
        ),
        "telegram": (
            "curl -sS --max-time 8 -o /dev/null -w 'HTTP %{http_code}\\n' "
            "https://api.telegram.org"
        ),
        "openrouter": (
            "curl -sS --max-time 8 -o /dev/null -w 'HTTP %{http_code}\\n' "
            "https://openrouter.ai/api/v1/models"
        ),
    }
    try:
        client.connect(
            str(values["IPV4"]),
            username=values["SSH_USER"],
            password=values["SSH_PASSWORD"],
            timeout=10,
            auth_timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        for name, command in checks.items():
            _, output, error = client.exec_command(command, timeout=20)
            print(name)
            print(output.read().decode()[:8000])
            failure = error.read().decode()
            if failure:
                print(failure[:300])
            if output.channel.recv_exit_status() != 0:
                raise RuntimeError(f"Server check failed: {name}")
    except (OSError, paramiko.SSHException) as exc:
        raise SystemExit(
            f"Server inspection blocked: {type(exc).__name__}"
        ) from None
    finally:
        client.close()


if __name__ == "__main__":
    main()
