import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from alembic import command
from alembic.config import Config
from dishka import make_async_container
from papilio.core.config import get_settings
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from portal_contracts.configuration import SettingScope, SettingValueWrite
from src.config.providers import task_providers
from src.config.settings import PortalAppSettings
from src.modules.configuration.domain.dtos import ConfigurationSeed
from src.modules.configuration.interfaces import (
    IConfigurationCommands,
    IConfigurationQueries,
    ISettingValueService,
)

OWNER = 140001


class ExternalTelegramHandler(BaseHTTPRequestHandler):
    media_files = []
    media_delivery_status = "sent"
    media_directory = None
    messages = []
    photos = []
    photo_attempts = []
    photo_delivery_status = "sent"
    delivery_status = "sent"

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/internal/messages":
            type(self).messages.append(body)
            status = type(self).delivery_status
            response = {
                "status": status,
                "message_id": len(self.messages) if status == "sent" else None,
            }
        elif self.path == "/internal/photos":
            type(self).photo_attempts.append(body)
            status = type(self).photo_delivery_status
            if status == "sent":
                type(self).photos.append(body)
            response = {
                "status": status,
                "message_id": 100 + len(self.photos)
                if status == "sent"
                else None,
            }
        elif self.path == "/internal/media/files":
            assert self.media_directory is not None
            path = (
                self.media_directory / str(body["job_id"]) / body["filename"]
            )
            assert path.is_file() and path.stat().st_size > 0
            type(self).media_files.append(body)
            response = {
                "status": self.media_delivery_status,
                "message_id": 200 + len(self.media_files),
                "file_id": "external-test-media-file",
            }
        else:
            response = {"ok": True}
        payload = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class Harness:
    def __init__(self, settings, runner, config_path, environment):
        self.settings = settings
        self.runner = runner
        self.config_path = config_path
        self.environment = environment
        self.processes = []
        self.logs = []

    @asynccontextmanager
    async def request(self):
        container = make_async_container(*task_providers(self.settings))
        try:
            async with container() as scope:
                yield scope
        finally:
            await container.close()

    def run(self, coroutine):
        return self.runner.run(coroutine)

    async def change(self, key, scope, value):
        async with self.request() as request:
            service = await request.get(ISettingValueService)
            current = await service.get(key, scope)
            result = await service.write(
                key,
                scope,
                SettingValueWrite(
                    revision=current.revision,
                    value=json.dumps(value),
                ),
            )
        return result

    async def snapshot(self):
        async with self.request() as request:
            query = await request.get(IConfigurationQueries)
            result = await query.snapshot()
        return result

    def start_workers(self, application="src.apps.scheduler"):
        env = {**os.environ, **self.environment}
        worker_log = self.config_path.with_suffix(".worker.log").open("w+")
        scheduler_log = self.config_path.with_suffix(".scheduler.log").open(
            "w+"
        )
        worker = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "taskiq",
                "worker",
                application + ":broker",
                "--workers",
                "1",
                "--max-async-tasks",
                "1" if application == "src.apps.media" else "8",
            ],
            env=env,
            stdout=worker_log,
            stderr=subprocess.STDOUT,
        )
        scheduler = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "taskiq",
                "scheduler",
                application + ":scheduler",
                "--update-interval",
                "5",
            ],
            env=env,
            stdout=scheduler_log,
            stderr=subprocess.STDOUT,
        )
        self.processes = [worker, scheduler]
        self.logs = [worker_log, scheduler_log]

    def until(self, read, condition, timeout=45):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            if any(process.poll() is not None for process in self.processes):
                for log in self.logs:
                    log.flush()
                    log.seek(0)
                    print(log.read()[-6000:])
                pytest.fail("Native worker/scheduler exited")
            last = self.run(read())
            if condition(last):
                return last
            time.sleep(0.15)
        pytest.fail(f"Background condition did not complete: {last}")


@pytest.fixture
def portal(tmp_path, tmp_path_factory, monkeypatch):
    database_url = os.getenv("PORTAL_TEST_DATABASE_URL")
    redis_url = os.getenv("PORTAL_TEST_REDIS_URL")
    if not database_url or not redis_url:
        pytest.skip(
            "Set isolated PORTAL_TEST_DATABASE_URL and PORTAL_TEST_REDIS_URL"
        )
    database = make_url(database_url)
    if database.get_backend_name() != "mysql":
        pytest.fail("Integration tests require MySQL")
    name = "portal_test_" + uuid4().hex
    owned_url = database.set(database=name).render_as_string(
        hide_password=False
    )
    runner = asyncio.Runner()
    admin = create_async_engine(database_url)

    async def create_database():
        async with admin.begin() as connection:
            await connection.execute(
                text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4")
            )

    runner.run(create_database())
    ExternalTelegramHandler.messages = []
    ExternalTelegramHandler.photos = []
    ExternalTelegramHandler.photo_attempts = []
    ExternalTelegramHandler.photo_delivery_status = "sent"
    ExternalTelegramHandler.delivery_status = "sent"
    ExternalTelegramHandler.media_files = []
    ExternalTelegramHandler.media_delivery_status = "sent"
    media_directory = tmp_path_factory.mktemp("media")
    ExternalTelegramHandler.media_directory = media_directory
    gateway = ThreadingHTTPServer(("127.0.0.1", 0), ExternalTelegramHandler)
    thread = threading.Thread(target=gateway.serve_forever, daemon=True)
    thread.start()
    namespace = "portal-test:" + uuid4().hex
    raw = yaml.safe_load(Path("config.yml.sample").read_text())
    raw["db"]["dsn"] = owned_url
    raw["portal"]["gateway_url"] = f"http://127.0.0.1:{gateway.server_port}"
    raw["media"] = {"directory": str(media_directory)}
    raw["tasks"].update(
        url=redis_url,
        queue_name=namespace + ":jobs",
        schedule_prefix=namespace + ":schedules",
        result_prefix=namespace + ":results",
        consumer_group=namespace + ":workers",
    )
    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(raw))
    environment = {
        "PAPILIO_CONFIG": str(config_path),
        "PORTAL_ENV_FILE": str(tmp_path / "unused.env"),
        "PORTAL_DATABASE_URL": owned_url,
        "PORTAL_REDIS_URL": redis_url,
        "PORTAL_SERVICE_KEY": "test-key-" * 8,
        "PORTAL_ADMIN_USER_IDS": str(OWNER),
        "PORTAL_DRY_RUN": "true",
        "OPENROUTER_API_KEY": "",
        "PYTHONPATH": os.pathsep.join(
            str(Path(path).resolve())
            for path in (
                "api",
                "bots",
                "packages/contracts",
            )
        ),
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    sys.modules.pop("src.apps.scheduler", None)
    sys.modules.pop("src.apps.media", None)
    config = Config("api/alembic.ini")
    config.set_main_option("sqlalchemy.url", owned_url.replace("%", "%%"))
    command.upgrade(config, "head")
    command.check(config)
    settings = get_settings(PortalAppSettings)
    harness = Harness(settings, runner, config_path, environment)

    async def seed_database():
        async with harness.request() as request:
            service = await request.get(IConfigurationCommands)
            await service.seed(
                ConfigurationSeed.model_validate_json(
                    Path("api/seeds/defaults.json").read_text()
                )
            )
            from papilio.infra.db.uow import MySQLUnitOfWork

            from src.cli.pricing_seed import seed_pricing

            unit = await request.get(MySQLUnitOfWork)
            await seed_pricing(unit, Path("api/seeds/pricing.json"))
        snapshot = await harness.snapshot()
        policy = snapshot.configuration.portal.model_dump(
            mode="json", exclude={"dry_run"}
        )
        policy.update(
            quiet_start="00:00", quiet_end="00:00", channel_id=-100140001
        )
        await harness.change("portal.policy", SettingScope.GLOBAL, policy)

    runner.run(seed_database())
    try:
        yield harness
    finally:
        for process in harness.processes:
            process.terminate()
        for process in harness.processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for log in harness.logs:
            log.close()
        gateway.shutdown()
        gateway.server_close()

        async def cleanup():
            from redis.asyncio import Redis

            scheduler_module = sys.modules.pop("src.apps.scheduler", None)
            if scheduler_module is not None:
                await scheduler_module.app.stop()
            media_module = sys.modules.pop("src.apps.media", None)
            if media_module is not None:
                await media_module.app.stop()
            client = Redis.from_url(redis_url)
            keys = await client.keys(namespace + "*")
            if keys:
                await client.delete(*keys)
            await client.aclose()
            async with admin.begin() as connection:
                await connection.execute(text(f"DROP DATABASE `{name}`"))
            await admin.dispose()

        runner.run(cleanup())
        runner.close()
        get_settings.cache_clear()
