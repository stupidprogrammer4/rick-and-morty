import os
import subprocess
import tempfile
from pathlib import Path

values = {
    "MYSQL_PASSWORD": "test-only-password",
    "MYSQL_ROOT_PASSWORD": "test-only-root-password",
    "PORTAL_DATABASE_URL": "mysql+aiomysql://portal:test@mysql:3306/portal",
    "PORTAL_SERVICE_KEY": "test-service-key-" * 4,
    "PORTAL_ADMIN_USER_IDS": "140001",
    "RICK_TG_BOT": "140001:TEST_ONLY_NOT_REAL",
    "MORTY_TG_BOT": "140002:TEST_ONLY_NOT_REAL",
    "PORTAL_RICK_WEBHOOK_SECRET": "rick-test-key-" * 4,
    "PORTAL_MORTY_WEBHOOK_SECRET": "morty-test-key-" * 4,
}
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / ".env"
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items())
    )
    subprocess.run(
        ["docker", "compose", "--env-file", str(path), "config", "--quiet"],
        env={**os.environ, **values},
        check=True,
    )
print("Compose configuration validated with synthetic credentials")
