import argparse
import asyncio
import os
from pathlib import Path

from dishka import make_async_container
from dotenv import load_dotenv
from papilio.core.config import get_settings
from papilio.infra.db.uow import MySQLUnitOfWork

from src.cli.pricing_seed import seed_pricing
from src.config.providers import task_providers
from src.config.settings import PortalAppSettings
from src.modules.ops.settings.domain.dtos import ConfigurationSeed
from src.modules.ops.settings.interfaces import IConfigurationCommands


async def seed(path: Path) -> None:
    data = ConfigurationSeed.model_validate_json(path.read_text())
    settings = get_settings(PortalAppSettings)
    container = make_async_container(*task_providers(settings))
    try:
        async with container() as request:
            commands = await request.get(IConfigurationCommands)
            await commands.seed(data)
            uow = await request.get(MySQLUnitOfWork)
            await seed_pricing(uow, Path("api/seeds/pricing.json"))
    finally:
        await container.close()
    print(
        "Seed completed; existing definitions, values and sources preserved."
    )


def main() -> None:
    load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file", type=Path, default=Path("api/seeds/defaults.json")
    )
    arguments = parser.parse_args()
    asyncio.run(seed(arguments.file))


if __name__ == "__main__":
    main()
