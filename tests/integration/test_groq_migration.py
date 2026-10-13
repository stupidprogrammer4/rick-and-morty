import importlib.util
import json
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def apply_provider_migration(connection):
    path = Path("api/migrations/versions/20261013_groq_model.py")
    spec = importlib.util.spec_from_file_location("groq_upgrade", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(connection)):
        module.upgrade()


async def check_upgrade(portal):
    engine = create_async_engine(portal.settings.db.dsn)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE tbl_setting_values v "
                    "JOIN tbl_setting_definitions d "
                    "ON d.id=v.definition_id SET v.value=JSON_SET(v.value, "
                    "'$.mode','openrouter','$.model','legacy/free:free', "
                    "'$.reasoning_effort','none'),v.revision=7 "
                    "WHERE d.`key`='ai.model'"
                )
            )
            prior = (
                await connection.execute(
                    text(
                        "SELECT v.value FROM tbl_setting_values v "
                        "JOIN tbl_setting_definitions d "
                        "ON d.id=v.definition_id "
                        "WHERE d.`key`='ai.model'"
                    )
                )
            ).scalar_one()
        async with engine.begin() as connection:
            await connection.run_sync(apply_provider_migration)
        async with engine.begin() as connection:
            value, revision = (
                await connection.execute(
                    text(
                        "SELECT v.value,v.revision FROM tbl_setting_values v "
                        "JOIN tbl_setting_definitions d "
                        "ON d.id=v.definition_id "
                        "WHERE d.`key`='ai.model'"
                    )
                )
            ).one()
        migrated = json.loads(value)
        assert migrated["mode"] == "groq"
        assert migrated["model"] == "qwen/qwen3.8-27b"
        assert migrated["reasoning_effort"] is None
        assert revision == 8
        assert migrated["max_requests"] == json.loads(prior)["max_requests"]
        assert (
            migrated["daily_budget_usd"]
            == json.loads(prior)["daily_budget_usd"]
        )
    finally:
        await engine.dispose()


def test_groq_upgrade_preserves_existing_budget_and_request_limits(portal):
    portal.runner.run(check_upgrade(portal))
