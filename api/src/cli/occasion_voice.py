"""Apply Rick's occasion voice and youth selection to live settings."""

import asyncio
import os

from dishka import make_async_container
from dotenv import load_dotenv
from papilio.core.config import get_settings
from papilio.infra.db.transaction import transaction
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import text

from portal_contracts.configuration import (
    SettingKey,
    SettingScope,
    SettingValueWrite,
)
from portal_contracts.enums import BotRole
from portal_contracts.occasions import (
    RICK_OCCASION_PROMPT,
    RICK_OCCASION_SYSTEM_PROMPT,
    OccasionPolicy,
)
from portal_contracts.presentation import PostStyle
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
                    SettingKey.OCCASIONS, SettingScope.GLOBAL
                )
                if record.value is None:
                    raise ValueError(
                        "Seed the occasion policy before upgrading"
                    )
                policy = OccasionPolicy.model_validate_json(record.value)
                policy.selection = "youth"
                policy.max_events = 3
                policy.system_prompt = RICK_OCCASION_SYSTEM_PROMPT
                policy.prompt = RICK_OCCASION_PROMPT
                await values.write(
                    SettingKey.OCCASIONS,
                    SettingScope.GLOBAL,
                    SettingValueWrite(
                        value=policy.model_dump_json(),
                        revision=record.revision,
                    ),
                )
                style = await values.get(
                    SettingKey.POST, SettingScope.OCCASIONS
                )
                await values.write(
                    SettingKey.POST,
                    SettingScope.OCCASIONS,
                    SettingValueWrite(
                        value=PostStyle(
                            publisher_bot=BotRole.RICK,
                            heading="",
                            separator="",
                            footer="",
                            hashtags="",
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
                        "WHERE m.intent='occasions' AND p.status='queued'"
                    )
                )
    finally:
        await container.close()
    print(
        "Rick occasion voice saved; youth selection, max 3; "
        "old queued posts cancelled."
    )


def main() -> None:
    load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
    asyncio.run(apply())


if __name__ == "__main__":
    main()
