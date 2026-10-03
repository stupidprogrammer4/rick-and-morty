import asyncio
import os

from dishka import make_async_container
from dotenv import load_dotenv
from papilio.core.bootstrap import Bootstrapper
from papilio.core.config import get_settings
from papilio.mcp.server import build_server

from src.config.providers import task_providers
from src.config.settings import PortalAppSettings


async def main() -> None:
    load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
    settings = get_settings(PortalAppSettings)
    container = make_async_container(*task_providers(settings))
    bootstrap = Bootstrapper(settings.app.modules)
    server = build_server(
        bootstrap.boot_mcp_tools(), container, name="Papilio Portal"
    )
    try:
        await server.run_stdio_async()
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
