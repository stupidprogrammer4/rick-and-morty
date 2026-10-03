import argparse
import asyncio
import os
from pathlib import Path

from dishka import make_async_container
from dotenv import load_dotenv
from papilio.core.config import get_settings

from src.config.providers import task_providers
from src.config.settings import PortalAppSettings
from src.modules.configuration.domain.dtos import ConfigurationSeed
from src.modules.configuration.interfaces import IConfigurationCommands


async def seed(path: Path) -> None:
    data = ConfigurationSeed.model_validate_json(path.read_text())
    settings = get_settings(PortalAppSettings)
    container = make_async_container(*task_providers(settings))
    try:
        async with container() as request:
            commands = await request.get(IConfigurationCommands)
            await commands.seed(data)
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
