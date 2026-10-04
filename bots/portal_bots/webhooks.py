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
    media = (
        Bot(settings.media_token.get_secret_value())
        if settings.media_token
        else None
    )
    try:
        identities = await asyncio.gather(rick.get_me(), morty.get_me())
        if identities[0].id == identities[1].id:
            raise ValueError("Rick and Morty need independent identities")
        if media is not None:
            identity = await media.get_me()
            if identity.id in {item.id for item in identities}:
                raise ValueError("Media needs an independent identity")
            if settings.media_webhook_secret is None:
                raise ValueError("Media webhook secret required")
            registered = await media.set_webhook(
                origin + "/telegram/media",
                secret_token=settings.media_webhook_secret.get_secret_value(),
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=False,
            )
            if not registered:
                raise RuntimeError("Media webhook registration failed")
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
        if media is not None:
            await media.session.close()


if __name__ == "__main__":
    asyncio.run(register())
