import argparse
import asyncio
import os

import httpx
from dishka import make_async_container
from dotenv import load_dotenv
from papilio.core.config import get_settings

from src.config.providers import task_providers
from src.config.settings import PortalAppSettings
from src.modules.configuration.interfaces import IConfigurationQueries
from src.modules.market.interfaces import IMarketQuery
from src.modules.rick.interfaces import IModelSmokeCommands


async def check(paid_model: bool) -> None:
    settings = get_settings(PortalAppSettings)
    container = make_async_container(*task_providers(settings))
    try:
        async with container() as request:
            query = await request.get(IConfigurationQueries)
            snapshot = await query.snapshot()
            print("Database configuration: loaded")
            print("Model:", snapshot.configuration.ai.model)
            print(
                "Publishing channel configured:",
                snapshot.configuration.portal.channel_id is not None,
            )
            client = await request.get(httpx.AsyncClient)
            response = await client.get(
                settings.portal.gateway_url + "/health/live"
            )
            response.raise_for_status()
            print("Bot gateway: reachable")
            market = await request.get(IMarketQuery)
            prices = await market.snapshot()
            print(
                "Market: all three quotes passed freshness and unit validation"
            )
            print(
                "Quote symbols:",
                ", ".join(quote.symbol for quote in prices.quotes),
            )
            if paid_model:
                identities = await client.get(
                    settings.portal.gateway_url + "/internal/identities",
                    headers={
                        "Authorization": "Bearer "
                        + settings.security.service_key.get_secret_value()
                    },
                )
                identities.raise_for_status()
                smoke = await request.get(IModelSmokeCommands)
                text = await smoke.run(
                    min(settings.security.admin_ids),
                    identities.json()["rick"]["id"],
                )
                print("OpenRouter live response:", text[:300])
                print(
                    "The smoke mission and its cost reservation are persisted."
                )

    finally:
        await container.close()


def main() -> None:
    load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--paid-model-smoke", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(check(args.paid_model_smoke))
    except Exception as exc:
        raise SystemExit(f"Live check failed: {type(exc).__name__}") from None


if __name__ == "__main__":
    main()
