import re

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from portal_bots.config.settings import BotSettings


class PrivateAdminMiddleware(BaseMiddleware):
    def __init__(self, settings: BotSettings):
        self.settings = settings

    async def __call__(self, handler, event, data):
        message = event.message if isinstance(event, CallbackQuery) else event
        user = (
            event.from_user
            if isinstance(event, (Message, CallbackQuery))
            else None
        )
        if (
            isinstance(event, CallbackQuery)
            and isinstance(message, Message)
            and message.chat.type == "channel"
            and user is not None
            and not user.is_bot
            and re.fullmatch(r"prices:[1-9][0-9]*:[0-9]+", event.data or "")
        ):
            result = await handler(event, data)
            return result
        if (
            not isinstance(message, Message)
            or message.chat.type != "private"
            or user is None
            or user.is_bot
            or user.id not in self.settings.admin_ids
            or message.chat.id != user.id
        ):
            if isinstance(event, CallbackQuery):
                await event.answer("این کنترل مخصوص پویاست.", show_alert=True)
            return None
        result = await handler(event, data)
        return result
