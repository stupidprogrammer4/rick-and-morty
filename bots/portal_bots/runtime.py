import asyncio
import base64
import logging
from hmac import compare_digest

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)
from aiogram.types import (
    BufferedInputFile,
    LinkPreviewOptions,
    ReactionTypeEmoji,
    ReplyParameters,
    Update,
)
from aiohttp import web
from pydantic import ValidationError

from portal_bots.app.pages import page_keyboard
from portal_bots.config.settings import BotSettings
from portal_bots.infra.backend import BackendClient, BackendUnavailable
from portal_bots.routers import drafts, missions, ops, pages
from portal_bots.routers import settings as settings_router
from portal_bots.routers.auth import PrivateAdminMiddleware
from portal_bots.routers.drafts import draft_keyboard
from portal_bots.routers.errors import CommandErrorMiddleware
from portal_bots.routers.presentation import PresentationMiddleware
from portal_contracts.configuration import BotConfiguration
from portal_contracts.enums import BotRole
from portal_contracts.telegram import (
    DeliveryResult,
    ReactionRequest,
    TelegramDelivery,
    TelegramPhotoDelivery,
    TypingRequest,
)


class BotRuntime:
    def __init__(self, settings: BotSettings):
        self.settings = settings
        properties = DefaultBotProperties(parse_mode="HTML")
        self.bots = {
            BotRole.RICK: Bot(
                settings.rick_token.get_secret_value(), default=properties
            ),
            BotRole.MORTY: Bot(
                settings.morty_token.get_secret_value(), default=properties
            ),
        }
        self.client = httpx.AsyncClient(trust_env=False)
        self.backend = BackendClient(self.client, settings)
        # Roles and updates stay local to each dispatcher request.
        self.dispatcher = Dispatcher()
        self.dispatcher.message.outer_middleware(
            PrivateAdminMiddleware(settings)
        )
        self.dispatcher.callback_query.outer_middleware(
            PrivateAdminMiddleware(settings)
        )
        self.dispatcher.message.outer_middleware(CommandErrorMiddleware())
        self.dispatcher.callback_query.outer_middleware(
            CommandErrorMiddleware()
        )
        self.dispatcher.message.outer_middleware(PresentationMiddleware())
        self.dispatcher.callback_query.outer_middleware(
            PresentationMiddleware()
        )
        self.dispatcher.include_routers(
            pages.router,
            ops.router,
            settings_router.router,
            drafts.router,
            missions.router,
        )

    async def startup(self, app: web.Application):
        identities = await asyncio.gather(
            *(bot.get_me() for bot in self.bots.values())
        )
        if len({identity.id for identity in identities}) != 2:
            raise RuntimeError("Rick and Morty resolve to the same identity")
        self.identities = {
            role.value: {"id": identity.id, "username": identity.username}
            for role, identity in zip(self.bots, identities, strict=True)
        }
        await self.dispatcher.emit_startup()

    async def cleanup(self, app: web.Application):
        await self.dispatcher.emit_shutdown()
        await asyncio.gather(
            *(bot.session.close() for bot in self.bots.values())
        )
        await self.client.aclose()

    async def webhook(self, request: web.Request):
        role = BotRole(request.match_info["role"])
        secret = (
            self.settings.rick_webhook_secret
            if role == BotRole.RICK
            else self.settings.morty_webhook_secret
        ).get_secret_value()
        if not compare_digest(
            request.headers.get(
                "X-Telegram-Bot-Api-Secret-Token", ""
            ).encode(),
            secret.encode(),
        ):
            raise web.HTTPUnauthorized()
        try:
            payload = await request.json()
            update = Update.model_validate(
                payload, context={"bot": self.bots[role]}
            )
        except (ValueError, ValidationError):
            raise web.HTTPBadRequest() from None
        try:
            await self.dispatcher.feed_update(
                self.bots[role],
                update,
                role=role,
                backend=self.backend,
                update_id=update.update_id,
                portal_admin_id=min(self.settings.admin_ids),
            )
        except BackendUnavailable:
            raise web.HTTPServiceUnavailable() from None
        return web.json_response({"ok": True})

    def authenticate(self, request: web.Request):
        if not compare_digest(
            request.headers.get("Authorization", "").encode(),
            (
                "Bearer " + self.settings.service_key.get_secret_value()
            ).encode(),
        ):
            raise web.HTTPUnauthorized()

    async def authorize_delivery(
        self, chat_id: int, publication_id: int | None
    ):
        if publication_id is not None:
            raw = await self.backend.request(
                "GET", "/configuration/bot", min(self.settings.admin_ids)
            )
            configuration = BotConfiguration.model_validate(raw)
            if chat_id != configuration.channel_id or chat_id == 0:
                raise web.HTTPForbidden()
        elif chat_id not in self.settings.admin_ids:
            raise web.HTTPForbidden()

    async def send(self, request: web.Request):
        self.authenticate(request)
        data = TelegramDelivery.model_validate(await request.json())
        await self.authorize_delivery(data.chat_id, data.publication_id)
        bot = self.bots[data.role]
        keyboard = None
        if data.draft_id is not None and data.revision is not None:
            keyboard = draft_keyboard(data.draft_id, data.revision, data.role)
        if data.navigation is not None:
            keyboard = page_keyboard(data.navigation)
        try:
            message = await bot.send_message(
                data.chat_id,
                data.text,
                reply_markup=keyboard,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            result = DeliveryResult(
                status="sent", message_id=message.message_id
            )
        except TelegramRetryAfter as exc:
            result = DeliveryResult(
                status="rate_limited",
                retry_after=exc.retry_after,
                reason="telegram_rate_limit",
            )
        except (
            TelegramBadRequest,
            TelegramForbiddenError,
            TelegramUnauthorizedError,
        ) as exc:
            result = DeliveryResult(status="failed", reason=type(exc).__name__)
        except (TelegramNetworkError, TimeoutError):
            result = DeliveryResult(
                status="unknown", reason="telegram_delivery_unknown"
            )
        return web.json_response(result.model_dump())

    async def send_photo(self, request: web.Request):
        self.authenticate(request)
        try:
            data = TelegramPhotoDelivery.model_validate(await request.json())
        except ValueError:
            raise web.HTTPBadRequest() from None
        await self.authorize_delivery(data.chat_id, data.publication_id)
        try:
            message = await self.bots[data.role].send_photo(
                chat_id=data.chat_id,
                photo=BufferedInputFile(
                    base64.b64decode(data.png_base64),
                    filename=f"asset-chart-{data.chart_id}.png",
                ),
                caption=data.caption,
                reply_parameters=ReplyParameters(
                    message_id=data.reply_to_message_id
                ),
            )
            result = DeliveryResult(
                status="sent", message_id=message.message_id
            )
        except TelegramRetryAfter as exc:
            result = DeliveryResult(
                status="rate_limited",
                retry_after=exc.retry_after,
                reason="telegram_rate_limit",
            )
        except (
            TelegramBadRequest,
            TelegramForbiddenError,
            TelegramUnauthorizedError,
        ) as exc:
            result = DeliveryResult(status="failed", reason=type(exc).__name__)
        except (TelegramNetworkError, TimeoutError):
            result = DeliveryResult(
                status="unknown", reason="telegram_photo_delivery_unknown"
            )
        return web.json_response(result.model_dump())

    async def react(self, request: web.Request):
        self.authenticate(request)
        data = ReactionRequest.model_validate(await request.json())
        if data.chat_id not in self.settings.admin_ids:
            raise web.HTTPForbidden()
        await self.bots[data.role].set_message_reaction(
            chat_id=data.chat_id,
            message_id=data.message_id,
            reaction=[ReactionTypeEmoji(emoji=data.emoji.value)],
        )
        return web.json_response({"ok": True})

    async def typing(self, request: web.Request):
        self.authenticate(request)
        data = TypingRequest.model_validate(await request.json())
        if data.chat_id not in self.settings.admin_ids:
            raise web.HTTPForbidden()
        await self.bots[data.role].send_chat_action(data.chat_id, "typing")
        return web.json_response({"ok": True})

    async def bot_identities(self, request: web.Request):
        self.authenticate(request)
        return web.json_response(self.identities)

    async def health(self, request: web.Request):
        return web.json_response({"status": "alive", "transport": "webhook"})

    def application(self):
        app = web.Application(client_max_size=512 * 1024)
        app.router.add_post("/telegram/{role:rick|morty}", self.webhook)
        app.router.add_post("/internal/messages", self.send)
        app.router.add_post("/internal/photos", self.send_photo)
        app.router.add_post("/internal/reactions", self.react)
        app.router.add_post("/internal/typing", self.typing)
        app.router.add_get("/health/live", self.health)
        app.router.add_get("/internal/identities", self.bot_identities)
        app.on_startup.append(self.startup)
        app.on_cleanup.append(self.cleanup)
        return app


def main():
    settings = BotSettings.from_env()
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    runtime = BotRuntime(settings)
    web.run_app(
        runtime.application(),
        host="0.0.0.0",
        port=settings.port,
        access_log=None,
        print=None,
    )
