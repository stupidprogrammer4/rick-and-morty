import re
from hmac import compare_digest
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import FSInputFile, Update
from aiohttp import web
from pydantic import BaseModel, Field

from portal_bots.config.settings import BotSettings
from portal_bots.infra.backend import BackendClient, BackendUnavailable
from portal_bots.media.configuration import MediaConfigurationMiddleware
from portal_bots.media.routers import make_router
from portal_bots.routers.errors import CommandErrorMiddleware
from portal_contracts.media import (
    MediaFileDelivery,
    MediaFileResult,
    MediaPolicy,
)


class MediaNotification(BaseModel):
    owner_id: int = Field(gt=0)
    text: str = Field(max_length=4000)


class MediaRuntime:
    def __init__(self, settings: BotSettings, backend: BackendClient):
        if (
            settings.media_token is None
            or settings.media_webhook_secret is None
        ):
            raise ValueError("Media credentials required")
        self.settings = settings
        self.backend = backend
        self.bot = Bot(
            settings.media_token.get_secret_value(),
            default=DefaultBotProperties(
                parse_mode="HTML", link_preview_is_disabled=True
            ),
        )
        storage = RedisStorage.from_url(
            settings.redis_url,
            key_builder=DefaultKeyBuilder(
                prefix="portal-media-fsm", with_bot_id=True
            ),
            data_ttl=3600,
        )
        self.dispatcher = Dispatcher(
            storage=storage, events_isolation=storage.create_isolation()
        )
        configuration = MediaConfigurationMiddleware()
        self.dispatcher.message.outer_middleware(CommandErrorMiddleware())
        self.dispatcher.callback_query.outer_middleware(
            CommandErrorMiddleware()
        )
        self.dispatcher.include_router(make_router())
        self.dispatcher.message.outer_middleware(configuration)
        self.dispatcher.callback_query.outer_middleware(configuration)

    async def webhook(self, request: web.Request):
        secret = self.settings.media_webhook_secret
        if secret is None or not compare_digest(
            request.headers.get(
                "X-Telegram-Bot-Api-Secret-Token", ""
            ).encode(),
            secret.get_secret_value().encode(),
        ):
            raise web.HTTPUnauthorized()
        try:
            update = Update.model_validate(
                await request.json(), context={"bot": self.bot}
            )
        except ValueError:
            raise web.HTTPBadRequest() from None
        try:
            await self.dispatcher.feed_update(
                self.bot,
                update,
                backend=self.backend,
                update_id=update.update_id,
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

    async def send_file(self, request: web.Request):
        self.authenticate(request)
        data = MediaFileDelivery.model_validate(await request.json())
        authorized = await self.backend.request(
            "POST",
            "/media/authorize-file",
            data.owner_id,
            data=data.model_dump(),
        )
        if not authorized.get("authorized"):
            raise web.HTTPForbidden()
        root = Path(self.settings.media_directory).resolve()
        path = root / str(data.job_id) / str(data.item_id) / data.filename
        if not data.file_id and (
            not path.is_file()
            or path.is_symlink()
            or path.parent.is_symlink()
            or not path.resolve().is_relative_to(root)
        ):
            raise web.HTTPBadRequest()
        raw = await self.backend.request("GET", "/media/policy", data.owner_id)
        policy = MediaPolicy.model_validate(raw)
        if not data.file_id and path.stat().st_size > policy.max_file_bytes:
            raise web.HTTPRequestEntityTooLarge(
                max_size=policy.max_file_bytes, actual_size=path.stat().st_size
            )
        label = (
            re.sub(r'[\x00-\x1f\\/:*?"<>|]', "-", data.title).strip()[:120]
            or "AMU media"
        )
        file = data.file_id or FSInputFile(path, filename=label + path.suffix)
        try:
            if data.kind == "audio":
                message = await self.bot.send_audio(
                    data.owner_id,
                    audio=file,
                    caption=data.caption,
                    title=data.title,
                    performer=data.performer,
                    request_timeout=280,
                )
                file_id = message.audio.file_id if message.audio else None
            elif data.kind == "video" and path.suffix == ".mp4":
                message = await self.bot.send_video(
                    data.owner_id,
                    video=file,
                    caption=data.caption,
                    supports_streaming=True,
                    request_timeout=280,
                )
                file_id = message.video.file_id if message.video else None
            elif (
                data.kind == "photo"
                and (data.file_id or path.stat().st_size < 10_000_000)
                and path.suffix in {".jpg", ".jpeg", ".png"}
            ):
                message = await self.bot.send_photo(
                    data.owner_id,
                    photo=file,
                    caption=data.caption,
                    request_timeout=280,
                )
                file_id = message.photo[-1].file_id if message.photo else None
            else:
                message = await self.bot.send_document(
                    data.owner_id,
                    document=file,
                    caption=data.caption,
                    request_timeout=280,
                )
                file_id = (
                    message.document.file_id if message.document else None
                )
            result = MediaFileResult(
                status="sent", message_id=message.message_id, file_id=file_id
            )
        except TelegramRetryAfter as exc:
            result = MediaFileResult(
                status="rate_limited",
                retry_after=exc.retry_after,
                reason="telegram_rate_limit",
            )
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            invalid_cache = (
                data.file_id
                and isinstance(exc, TelegramBadRequest)
                and any(
                    marker in str(exc).lower()
                    for marker in (
                        "wrong file identifier",
                        "file_id not found",
                        "wrong remote file identifier",
                        "file reference expired",
                    )
                )
            )
            result = MediaFileResult(
                status="cache_miss" if invalid_cache else "failed",
                reason=type(exc).__name__,
            )
        except (TelegramNetworkError, TimeoutError):
            result = MediaFileResult(
                status="unknown", reason="media_delivery_unknown"
            )
        return web.json_response(result.model_dump())

    async def notify(self, request: web.Request):
        self.authenticate(request)
        data = MediaNotification.model_validate(await request.json())
        try:
            await self.bot.send_message(data.owner_id, data.text)
        except (
            TelegramBadRequest,
            TelegramForbiddenError,
            TelegramRetryAfter,
            TelegramNetworkError,
        ):
            pass
        return web.json_response({"ok": True})

    def attach(self, app: web.Application):
        app.router.add_post("/telegram/media", self.webhook)
        app.router.add_post("/internal/media/files", self.send_file)
        app.router.add_post("/internal/media/notifications", self.notify)
