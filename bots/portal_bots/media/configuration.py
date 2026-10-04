from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from portal_bots.interfaces import IBackendClient
from portal_contracts.media import MediaPolicy


class MediaConfigurationMiddleware(BaseMiddleware):
    def __init__(self):
        self.policy: MediaPolicy | None = None
        self.expires = 0.0

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        message = (
            event
            if isinstance(event, Message)
            else event.message
            if isinstance(event, CallbackQuery)
            else None
        )
        if message is None or message.chat.type != "private":
            return None
        backend: IBackendClient = data["backend"]
        if self.policy is None or monotonic() >= self.expires:
            raw = await backend.request(
                "GET", "/media/policy", message.chat.id
            )
            self.policy = MediaPolicy.model_validate(raw)
            self.expires = monotonic() + 30
        data["media_policy"] = self.policy
        result = await handler(event, data)
        return result
