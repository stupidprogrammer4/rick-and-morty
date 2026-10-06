"""Report or apply the same 24-hour cleanup used by the minute scheduler."""

import argparse
import asyncio
import json
import os

from dishka import make_async_container
from dotenv import load_dotenv
from papilio.core.config import get_settings

from src.config.providers import task_providers
from src.config.settings import PortalAppSettings
from src.modules.pricing.retention.app.maintenance import (
    PricingHistoryMaintenance,
)


async def run(
    *, apply: bool, batch_size: int, max_batches_per_table: int
) -> dict:
    settings = get_settings(PortalAppSettings)
    container = make_async_container(*task_providers(settings))
    try:
        async with container() as scope:
            maintenance = await scope.get(PricingHistoryMaintenance)
            if not apply:
                return {"dry_run": True, **await maintenance.stats()}
            removed = await maintenance.clean(
                batch_size=batch_size,
                max_batches_per_table=max_batches_per_table,
            )
            return {
                "dry_run": False,
                **removed,
                "remaining_expired_rows": (await maintenance.stats())[
                    "expired_rows"
                ],
            }
    finally:
        await container.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Delete expired pricing history"
    )
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--max-batches-per-table", type=int, default=100)
    arguments = parser.parse_args()
    if not 1 <= arguments.batch_size <= 10000:
        parser.error("--batch-size must be 1..10000")
    if not 1 <= arguments.max_batches_per_table <= 10000:
        parser.error("--max-batches-per-table must be 1..10000")
    load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
    result = asyncio.run(
        run(
            apply=arguments.apply,
            batch_size=arguments.batch_size,
            max_batches_per_table=arguments.max_batches_per_table,
        )
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
