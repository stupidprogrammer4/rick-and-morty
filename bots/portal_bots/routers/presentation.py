from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from portal_bots.app.voice import BotVoice
from portal_contracts.configuration import BotConfiguration


class PresentationMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, CallbackQuery) and (event.data or "").startswith(
            "prices:"
        ):
            result = await handler(event, data)
            return result
        if (
            isinstance(event, (Message, CallbackQuery))
            and event.from_user is not None
        ):
            raw = await data["backend"].request(
                "GET", "/configuration/bot", event.from_user.id
            )
            configuration = BotConfiguration.model_validate(raw)
            data["voice"] = BotVoice(configuration.presentation)
        result = await handler(event, data)
        return result
