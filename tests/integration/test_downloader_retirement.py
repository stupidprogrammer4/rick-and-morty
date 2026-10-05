import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from papilio.core.config import get_settings
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration


def test_retirement_preserves_previous_data_and_refuses_active_jobs(
    monkeypatch, tmp_path
):
    database_url = os.getenv("PORTAL_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set isolated PORTAL_TEST_DATABASE_URL")
    name = "portal_upgrade_" + uuid4().hex
    original = make_url(database_url)
    if original.get_backend_name() != "mysql":
        pytest.fail("Integration tests require MySQL")
    url = original.set(database=name).render_as_string(hide_password=False)
    admin = create_async_engine(database_url)
    engine = create_async_engine(url)
    monkeypatch.setenv(
        "PAPILIO_CONFIG", str(Path("config.yml.sample").resolve())
    )
    monkeypatch.setenv("PORTAL_ENV_FILE", str(tmp_path / "unused.env"))
    monkeypatch.setenv("PORTAL_DATABASE_URL", url)
    monkeypatch.setenv("PORTAL_SERVICE_KEY", "test-key-" * 8)
    monkeypatch.setenv("PORTAL_ADMIN_USER_IDS", "140001")
    get_settings.cache_clear()
    runner = asyncio.Runner()
    config = Config("api/alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))

    async def create_database():
        async with admin.begin() as connection:
            await connection.execute(text(f"CREATE DATABASE `{name}`"))

    async def populate():
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO tbl_setting_definitions "
                    "(id, `key`, title, kind) "
                    "VALUES (101, 'media.policy', 'Custom policy', 'json')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO tbl_setting_values "
                    "(id, definition_id, scope, value, revision) "
                    "VALUES (102, 101, 'global', :policy, 23)"
                ),
                {"policy": '{"custom":true}'},
            )
            await connection.execute(
                text(
                    "INSERT INTO tbl_media_jobs "
                    "(id, owner_id, chat_id, bot_id, update_id, url, "
                    "mode, provider, status, total, sent, failed) "
                    "VALUES (103, 140001, 140001, 140003, 42, "
                    "'https://example.com/audio.mp3', 'audio', 'direct', "
                    "'queued', 1, 0, 0)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO tbl_media_items "
                    "(id, job_id, position, title, payload, "
                    "source_url, status) "
                    "VALUES (104, 103, 1, 'Original item', '{}', "
                    "'https://example.com/audio.mp3', 'queued')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO tbl_media_assets "
                    "(id, cache_key, bot_id, file_id, payload, expires_at) "
                    "VALUES (105, 'original-key', 140003, 'original-file', "
                    "'{}', '2030-01-01')"
                )
            )

    async def finish_job():
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE tbl_media_jobs SET status='completed' WHERE id=103"
                )
            )

    async def verify():
        async with engine.connect() as connection:
            policy = (
                await connection.execute(
                    text(
                        "SELECT value, revision FROM archive_downloader_values"
                    )
                )
            ).one()
            assert policy == ('{"custom":true}', 23)
            definition = (
                await connection.execute(
                    text(
                        "SELECT id, title FROM archive_downloader_definitions"
                    )
                )
            ).one()
            assert definition == (101, "Custom policy")
            item = (
                await connection.execute(
                    text(
                        "SELECT i.id, i.title, j.id, j.owner_id "
                        "FROM archive_downloader_items i "
                        "JOIN archive_downloader_jobs j ON j.id=i.job_id"
                    )
                )
            ).one()
            assert item == (104, "Original item", 103, 140001)
            asset = (
                await connection.execute(
                    text("SELECT id, file_id FROM archive_downloader_assets")
                )
            ).one()
            assert asset == (105, "original-file")
            active = (
                await connection.execute(
                    text(
                        "SELECT COUNT(*) FROM tbl_setting_definitions "
                        "WHERE `key`='media.policy'"
                    )
                )
            ).scalar_one()
            assert active == 0

    async def cleanup():
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f"DROP DATABASE `{name}`"))
        await admin.dispose()

    async def add_conflicting_setting():
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO tbl_setting_definitions "
                    "(id, `key`, title, kind) "
                    "VALUES (101, 'portal.policy', 'Live setting', 'json')"
                )
            )

    async def remove_conflicting_setting():
        async with engine.begin() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT title FROM tbl_setting_definitions "
                        "WHERE id=101"
                    )
                )
            ).scalar_one()
            assert row == "Live setting"
            await connection.execute(
                text("DELETE FROM tbl_setting_definitions WHERE id=101")
            )

    async def verify_restored():
        async with engine.connect() as connection:
            item = (
                await connection.execute(
                    text(
                        "SELECT i.id, i.title, j.id, j.owner_id "
                        "FROM tbl_media_items i JOIN tbl_media_jobs j "
                        "ON j.id=i.job_id"
                    )
                )
            ).one()
            assert item == (104, "Original item", 103, 140001)
            policy = (
                await connection.execute(
                    text("SELECT value, revision FROM tbl_setting_values")
                )
            ).one()
            assert policy == ('{"custom":true}', 23)
            asset = (
                await connection.execute(
                    text("SELECT id, file_id FROM tbl_media_assets")
                )
            ).one()
            assert asset == (105, "original-file")

    runner.run(create_database())
    try:
        command.upgrade(config, "20261005_media_exit")
        runner.run(populate())
        with pytest.raises(RuntimeError, match="active downloads"):
            command.upgrade(config, "head")
        runner.run(finish_job())
        command.upgrade(config, "head")
        command.check(config)
        runner.run(verify())
        runner.run(add_conflicting_setting())
        with pytest.raises(RuntimeError, match="conflict"):
            command.downgrade(config, "20261005_media_exit")
        runner.run(verify())
        runner.run(remove_conflicting_setting())
        command.downgrade(config, "20261005_media_exit")
        runner.run(verify_restored())
        command.upgrade(config, "head")
        command.check(config)
        runner.run(verify())
    finally:
        runner.run(cleanup())
        runner.close()
        get_settings.cache_clear()
