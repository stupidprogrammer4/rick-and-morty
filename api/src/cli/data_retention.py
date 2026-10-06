"""Inspect or apply the bot's rolling 24-hour variable-data retention."""

import argparse
import asyncio
import json
import os

from dishka import make_async_container
from dotenv import load_dotenv
from papilio.core.config import get_settings

from src.config.providers import task_providers
from src.config.settings import PortalAppSettings
from src.modules.ops.queues.interfaces import ITaskHistoryMaintenance
from src.modules.ops.retention.app.maintenance import BotHistoryMaintenance
from src.modules.pricing.retention.app.maintenance import (
    PricingHistoryMaintenance,
)


async def run(*, apply: bool = False) -> dict:
    container = make_async_container(
        *task_providers(get_settings(PortalAppSettings))
    )
    try:
        async with container() as scope:
            history = await scope.get(BotHistoryMaintenance)
            prices = await scope.get(PricingHistoryMaintenance)
            if not apply:
                return {
                    "dry_run": True,
                    "history": await history.stats(),
                    "prices": await prices.stats(),
                }
            return {
                "dry_run": False,
                "history": await history.clean(max_batches_per_table=1000),
                "prices": await prices.clean(max_batches_per_table=1000),
                "task_history_removed": await (
                    await scope.get(ITaskHistoryMaintenance)
                ).clean(),
                "remaining_history": await history.stats(),
                "remaining_prices": await prices.stats(),
            }
    finally:
        await container.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False))


if __name__ == "__main__":
    main()
