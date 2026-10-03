import argparse
import io
import re
import shlex
import subprocess
from pathlib import Path

import paramiko
from check_server import PinnedHostKey
from dotenv import dotenv_values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument(
        "--runtime-env", type=Path, default=Path(".env.runtime")
    )
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path.home() / "w/Personal/papilio-proxy/.env",
    )
    args = parser.parse_args()
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=args.source, text=True
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise SystemExit("A committed release is required")
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar.gz", "HEAD"], cwd=args.source
    )
    credentials = dotenv_values(args.credentials)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(
        PinnedHostKey(str(credentials["SSH_HOST_KEY_SHA256"]))
    )
    try:
        client.connect(
            str(credentials["IPV4"]),
            username=credentials["SSH_USER"],
            password=credentials["SSH_PASSWORD"],
            timeout=10,
            auth_timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        _, output, _ = client.exec_command(
            "docker compose version >/dev/null && "
            "test -r /etc/letsencrypt/live/bot.amupouya.org/fullchain.pem "
            "&& nginx -t >/dev/null 2>&1 && "
            "mkdir -p /opt/portal/private /opt/portal/releases && "
            "chmod 700 /opt/portal/private && "
            "mktemp -d /tmp/portal-release.XXXXXXXX",
            timeout=20,
        )
        temporary = output.read().decode().strip()
        if output.channel.recv_exit_status() != 0 or not re.fullmatch(
            r"/tmp/portal-release\.[A-Za-z0-9]+", temporary
        ):
            raise RuntimeError(
                "Server requires Docker Compose and verified TLS ingress"
            )
        sftp = client.open_sftp()
        try:
            sftp.putfo(
                io.BytesIO(archive), temporary + "/portal-release.tar.gz"
            )
            sftp.put(str(args.images), temporary + "/portal-images.env")
            # Retain server credentials and database passwords on later runs.
            for source, destination in (
                (args.runtime_env, "/opt/portal/private/.env.runtime"),
                (args.config, "/opt/portal/private/config.yml"),
            ):
                try:
                    sftp.stat(destination)
                except FileNotFoundError:
                    with sftp.open(destination, "x") as target:
                        sftp.chmod(destination, 0o600)
                        target.write(source.read_bytes())
        finally:
            sftp.close()
        quoted = shlex.quote(temporary)
        _, output, _ = client.exec_command(
            f"tar -xzf {quoted}/portal-release.tar.gz -C {quoted} && "
            f"bash {quoted}/deploy/release.sh {quoted} {revision}",
            timeout=1200,
        )
        # Runtime errors may include URLs or secrets: print only the status.
        output.read()
        if output.channel.recv_exit_status() != 0:
            raise RuntimeError("Remote release failed; inspect private logs")
        print("Release deployed and verified; both webhooks registered")
    except (OSError, paramiko.SSHException, RuntimeError) as exc:
        raise SystemExit(f"Deployment stopped: {type(exc).__name__}") from None
    finally:
        client.close()


if __name__ == "__main__":
    main()
