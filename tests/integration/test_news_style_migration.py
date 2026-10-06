import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from portal_contracts.configuration import SettingScope
from portal_contracts.occasions import OccasionPolicy
from portal_contracts.rick_voice import (
    NEWS_POST_STYLE,
    RICK_NEWS_PROMPT,
    RICK_NEWS_SYSTEM_PROMPT,
)

pytestmark = pytest.mark.integration


def test_existing_settings_upgrade_preserves_clocks_and_calendar_choices(
    portal,
):
    path = Path("api/migrations/versions/20261006_restore_news_style.py")
    spec = importlib.util.spec_from_file_location("restore_news_style", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    async def workflow():
        before = (await portal.snapshot()).configuration
        automation = before.automation.model_dump(mode="json")
        automation["prices"]["interval_seconds"] = 3600
        automation["charts"]["interval_seconds"] = 14400
        automation["news"]["prompt"] = "Old forced news prompt"
        automation["news"]["system_prompt"] = "Old forced news persona"
        await portal.change(
            "automation.policy", SettingScope.GLOBAL, automation
        )
        occasions = before.occasions.model_dump(mode="json")
        occasions["system_prompt"] = "Old calendar system. " * 10
        occasions["prompt"] = "Old task"
        await portal.change("occasions.policy", SettingScope.GLOBAL, occasions)
        await portal.change(
            "post.style",
            SettingScope.NEWS,
            {
                "publisher_bot": "rick",
                "heading": "",
                "separator": "",
                "footer": "",
                "hashtags": "",
            },
        )
        old = (await portal.snapshot()).configuration
        engine = create_async_engine(portal.environment["PORTAL_DATABASE_URL"])
        try:
            async with engine.begin() as connection:
                await connection.run_sync(module.apply_style)
            # Reapplication must be harmless and not reset any clock or choice.
            async with engine.begin() as connection:
                await connection.run_sync(module.apply_style)
        finally:
            await engine.dispose()
        snapshot = await portal.snapshot()
        new = snapshot.configuration
        assert new.portal == old.portal
        assert new.automation.prices == old.automation.prices
        assert new.automation.charts == old.automation.charts
        assert new.automation.news.starts_at == old.automation.news.starts_at
        assert new.automation.news.enabled == old.automation.news.enabled
        assert (
            new.automation.news.interval_seconds
            == old.automation.news.interval_seconds
        )
        assert new.automation.owner_id == old.automation.owner_id
        assert new.automation.news.prompt == RICK_NEWS_PROMPT
        assert new.automation.news.system_prompt == RICK_NEWS_SYSTEM_PROMPT
        assert new.occasions.model_dump(
            exclude={"system_prompt", "prompt"}
        ) == old.occasions.model_dump(exclude={"system_prompt", "prompt"})
        assert new.occasions.system_prompt == OccasionPolicy().system_prompt
        assert new.occasions.prompt == OccasionPolicy().prompt
        assert (
            snapshot.presentation.posts["news"].model_dump() == NEWS_POST_STYLE
        )

    portal.run(workflow())
