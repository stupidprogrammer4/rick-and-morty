import asyncio
from urllib.parse import urlsplit

from aiogram import Bot

from portal_bots.config.settings import BotSettings


async def register() -> None:
    settings = BotSettings.from_env()
    origin = settings.webhook_base_url.rstrip("/")
    if urlsplit(origin).scheme != "https":
        raise ValueError(
            "PORTAL_WEBHOOK_BASE_URL must be a public HTTPS origin"
        )
    rick = Bot(settings.rick_token.get_secret_value())
    morty = Bot(settings.morty_token.get_secret_value())
    try:
        identities = await asyncio.gather(rick.get_me(), morty.get_me())
        if identities[0].id == identities[1].id:
            raise ValueError("Rick and Morty need independent identities")
        results = await asyncio.gather(
            rick.set_webhook(
                origin + "/telegram/rick",
                secret_token=settings.rick_webhook_secret.get_secret_value(),
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=False,
            ),
            morty.set_webhook(
                origin + "/telegram/morty",
                secret_token=settings.morty_webhook_secret.get_secret_value(),
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=False,
            ),
        )
        if not all(results):
            raise RuntimeError(
                "Webhook registration did not succeed for both bots"
            )
        print(
            "Both independent webhooks registered; pending updates retained."
        )
    finally:
        await asyncio.gather(rick.session.close(), morty.session.close())


if __name__ == "__main__":
    asyncio.run(register())
