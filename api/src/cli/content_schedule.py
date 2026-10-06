"""Apply the requested cadence to existing scoped database records."""

import argparse
import asyncio
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

from dishka import make_async_container
from dotenv import load_dotenv
from papilio.core.config import get_settings
from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import (
    PortalConfiguration,
    SettingKey,
    SettingScope,
    SettingValueWrite,
)
from src.config.providers import task_providers
from src.config.settings import PortalAppSettings
from src.modules.ops.guards.interfaces import IPortalGuard
from src.modules.ops.settings.interfaces import (
    IConfigurationQueries,
    ISettingValueService,
)
from src.shared.dates import utc_now


def cadence_values(
    current: PortalConfiguration, owner_id: int, now: datetime
) -> dict[SettingKey, str]:
    """Preserve content, sources and presentation while changing timing."""
    portal = current.portal.model_dump(exclude={"dry_run"})
    portal.update(
        timezone="Asia/Tehran",
        daily_post_cap=max(45, current.portal.daily_post_cap),
        quiet_start=time(0),
        quiet_end=time(0),
    )
    anchor = datetime.combine(
        now.astimezone(ZoneInfo("Asia/Tehran")).date(),
        time(10),
        ZoneInfo("Asia/Tehran"),
    )
    automation = current.automation.model_dump()
    automation["owner_id"] = owner_id
    for name, interval in (
        ("prices", 3600),
        ("news", 7200),
        ("charts", 10800),
    ):
        automation[name].update(
            enabled=True, interval_seconds=interval, starts_at=anchor
        )
        if name != "charts":
            automation[name]["lookback_seconds"] = interval
    occasions = current.occasions.model_dump()
    occasions.update(
        enabled=True,
        owner_id=owner_id,
        time=time(10),
        publish_start=time(15),
        publish_end=time(18),
    )
    market = current.market.model_dump()
    market["enabled"] = True
    market["charts"]["enabled"] = True
    from portal_contracts.configuration import (
        AutomationPolicy,
        MarketPolicy,
        PortalPolicy,
    )
    from portal_contracts.occasions import OccasionPolicy

    return {
        SettingKey.PORTAL: PortalPolicy.model_validate(
            portal
        ).model_dump_json(),
        SettingKey.AUTOMATION: AutomationPolicy.model_validate(
            automation
        ).model_dump_json(),
        SettingKey.OCCASIONS: OccasionPolicy.model_validate(
            occasions
        ).model_dump_json(),
        SettingKey.MARKET: MarketPolicy.model_validate(
            market
        ).model_dump_json(),
    }


async def apply(owner_id: int | None) -> None:
    runtime = get_settings(PortalAppSettings)
    container = make_async_container(*task_providers(runtime))
    try:
        async with container() as request:
            queries = await request.get(IConfigurationQueries)
            values = await request.get(ISettingValueService)
            guard = await request.get(IPortalGuard)
            async with transaction():
                await guard.lock("configuration")
                current = (await queries.snapshot()).configuration
                owner = (
                    owner_id
                    or current.automation.owner_id
                    or min(runtime.security.admin_ids)
                )
                if owner not in runtime.security.admin_ids:
                    raise ValueError("Schedule owner must be an administrator")
                if current.portal.channel_id is None:
                    raise ValueError("Configure the publishing channel first")
                for key, value in cadence_values(
                    current, owner, utc_now()
                ).items():
                    record = await values.get(key, SettingScope.GLOBAL)
                    await values.write(
                        key,
                        SettingScope.GLOBAL,
                        SettingValueWrite(
                            value=value, revision=record.revision
                        ),
                    )
    finally:
        await container.close()
    print(
        "Cadence saved (Asia/Tehran): prices 1h, charts 3h, news 2h; "
        "occasions prepare 10:00, randomized publication 15:00–18:00."
    )


def main() -> None:
    load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-id", type=int)
    arguments = parser.parse_args()
    asyncio.run(apply(arguments.owner_id))


if __name__ == "__main__":
    main()
