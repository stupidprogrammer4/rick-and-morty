"""Restore the earlier sourced news style without changing schedules."""

import asyncio
import os

from dishka import make_async_container
from dotenv import load_dotenv
from papilio.core.config import get_settings
from papilio.infra.db.transaction import transaction
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import text

from portal_contracts.configuration import (
    AutomationPolicy,
    SettingKey,
    SettingScope,
    SettingValueWrite,
)
from portal_contracts.presentation import PostStyle
from portal_contracts.rick_voice import (
    NEWS_POST_STYLE,
    RICK_NEWS_PROMPT,
    RICK_NEWS_SYSTEM_PROMPT,
)
from src.config.providers import task_providers
from src.config.settings import PortalAppSettings
from src.modules.ops.guards.interfaces import IPortalGuard
from src.modules.ops.settings.interfaces import ISettingValueService


async def apply() -> None:
    container = make_async_container(
        *task_providers(get_settings(PortalAppSettings))
    )
    try:
        async with container() as request:
            values = await request.get(ISettingValueService)
            guard = await request.get(IPortalGuard)
            uow = await request.get(MySQLUnitOfWork)
            async with transaction():
                await guard.lock("configuration")
                record = await values.get(
                    SettingKey.AUTOMATION, SettingScope.GLOBAL
                )
                if record.value is None:
                    raise ValueError(
                        "Seed automation settings before upgrading"
                    )
                policy = AutomationPolicy.model_validate_json(record.value)
                policy.news.system_prompt = RICK_NEWS_SYSTEM_PROMPT
                policy.news.prompt = RICK_NEWS_PROMPT
                await values.write(
                    SettingKey.AUTOMATION,
                    SettingScope.GLOBAL,
                    SettingValueWrite(
                        value=policy.model_dump_json(),
                        revision=record.revision,
                    ),
                )
                style = await values.get(SettingKey.POST, SettingScope.NEWS)
                await values.write(
                    SettingKey.POST,
                    SettingScope.NEWS,
                    SettingValueWrite(
                        value=PostStyle.model_validate(
                            NEWS_POST_STYLE
                        ).model_dump_json(),
                        revision=style.revision,
                    ),
                )
                await guard.lock("publishing")
                await uow.execute(
                    text(
                        "UPDATE tbl_publications p "
                        "JOIN tbl_drafts d ON d.id=p.draft_id "
                        "JOIN tbl_missions m ON m.id=d.mission_id "
                        "SET p.status='cancelled' "
                        "WHERE m.intent='news' AND p.status='queued'"
                    )
                )
    finally:
        await container.close()
    print(
        "Previous news style restored; schedules retained; "
        "old queued news cancelled."
    )


def main() -> None:
    load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
    asyncio.run(apply())


if __name__ == "__main__":
    main()
