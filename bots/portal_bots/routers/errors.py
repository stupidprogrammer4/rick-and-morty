from html import escape

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from portal_bots.app.voice import BotVoice
from portal_bots.infra.backend import BackendUnavailable


class CommandErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            result = await handler(event, data)
        except (ValueError, BackendUnavailable) as exc:
            if isinstance(exc, BackendUnavailable) and exc.retryable:
                raise
            voice: BotVoice | None = data.get("voice")
            text = (
                voice.error(data["role"], str(exc)[:500])
                if voice
                else str(exc)[:500]
            )
            if isinstance(event, CallbackQuery):
                await event.answer(text[:200], show_alert=True)
            elif isinstance(event, Message):
                await event.answer(escape(text))
            return None
        return result
