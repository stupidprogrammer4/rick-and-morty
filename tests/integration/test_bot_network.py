import json
import os
import subprocess
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration

BOT_SESSION = """
import asyncio
from portal_bots.config.settings import BotSettings
from portal_bots.runtime import BotRuntime
async def main():
    settings = BotSettings.from_env()
    assert settings.redis_url == "redis://redis:6379/1?socket_connect_timeout=2"
    runtime = BotRuntime(settings)
    try:
        assert runtime.media is not None
        await runtime.media.dispatcher.emit_startup()
        context = runtime.media.dispatcher.fsm.get_context(
            bot=runtime.media.bot, chat_id=140001, user_id=140001,
        )
        await context.update_data(mode='audio')
        data = await context.get_data()
        assert data['mode'] == 'audio'
        await context.clear()
        cleared = await context.get_data()
        assert not cleared
        print('Bot image session persisted and cleared through native Redis')
    finally:
        await runtime.cleanup(None)
asyncio.run(main())
"""


def test_bot_image_session_uses_declared_redis_network(tmp_path):
    image = os.getenv("PORTAL_BOT_TEST_IMAGE")
    if not image:
        pytest.skip("Requires the built bot image")
    environment = {
        **os.environ,
        "PORTAL_BOTS_IMAGE": image,
        "MYSQL_PASSWORD": "test-only-password",
        "MYSQL_ROOT_PASSWORD": "test-only-root-password",
        "PORTAL_DATABASE_URL": "mysql+aiomysql://portal:test@mysql/portal",
        "PORTAL_REDIS_URL": "redis://redis:6379/1?socket_connect_timeout=2",
        "PORTAL_SERVICE_KEY": "test-service-key-" * 4,
        "PORTAL_ADMIN_USER_IDS": "140001",
        "RICK_TG_BOT": "140001:TEST_ONLY_NOT_REAL",
        "MORTY_TG_BOT": "140002:TEST_ONLY_NOT_REAL",
        "MEDIA_DOWNLOADER_TG_BOT": "140003:TEST_ONLY_NOT_REAL",
        "PORTAL_RICK_WEBHOOK_SECRET": "rick-test-key-" * 4,
        "PORTAL_MORTY_WEBHOOK_SECRET": "morty-test-key-" * 4,
        "PORTAL_MEDIA_WEBHOOK_SECRET": "media-test-key-" * 4,
    }
    rendered = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            "/dev/null",
            "config",
            "--format",
            "json",
        ],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    configuration = json.loads(rendered.stdout)
    bots = configuration["services"]["bots"]
    redis = configuration["services"]["redis"]
    bots.pop("build", None)
    bots.pop("healthcheck", None)
    bots.pop("ports", None)
    bots["volumes"] = []
    bots["depends_on"].pop("api", None)
    bots["command"] = ["python", "-c", BOT_SESSION]
    bots["restart"] = "no"
    redis["volumes"] = []
    project = "portal-bot-network-" + uuid4().hex[:12]
    for name, network in configuration["networks"].items():
        network["name"] = project + "_" + name
    path = tmp_path / "compose.json"
    path.write_text(
        json.dumps(
            {
                "services": {"bots": bots, "redis": redis},
                "networks": configuration["networks"],
            }
        )
    )
    command = ["docker", "compose", "-p", project, "-f", str(path)]
    try:
        subprocess.run(
            command + ["up", "-d", "--wait", "redis"],
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )
        result = subprocess.run(
            command + ["run", "--rm", "--no-deps", "bots"],
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "persisted and cleared" in result.stdout
    finally:
        subprocess.run(
            command + ["down", "--volumes", "--remove-orphans"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
