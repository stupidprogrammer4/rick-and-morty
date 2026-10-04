import json
from datetime import UTC, datetime

import httpx
import pytest
from aiogram.client.telegram import TelegramAPIServer
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from papilio.api.application import create_app
from pydantic import SecretStr

from portal_bots.config.settings import BotSettings
from portal_bots.infra.backend import BackendClient
from portal_bots.media.runtime import MediaRuntime
from src.config.providers import infrastructure_providers
from src.modules.media.interfaces import IMediaQueries
from tests.integration.conftest import OWNER

pytestmark = pytest.mark.integration
USER = 140099


def test_public_webhook_menu_avatar_admission_and_cancel_use_native_api(
    portal,
):
    async def workflow():
        calls = []

        async def telegram(request):
            fields = await request.post()
            method = request.match_info["method"]
            if method == "answerCallbackQuery":
                return web.json_response({"ok": True, "result": True})
            result = {
                "message_id": len(calls) + 1,
                "date": int(datetime.now(UTC).timestamp()),
                "chat": {"id": int(fields["chat_id"]), "type": "private"},
            }
            if method == "sendPhoto":
                reference = fields["photo"]
                assert isinstance(reference, str)
                upload = fields[reference.removeprefix("attach://")]
                assert isinstance(upload, web.FileField)
                assert upload.file.read().startswith(b"\x89PNG")
                result["photo"] = [
                    {
                        "file_id": "avatar",
                        "file_unique_id": "avatar-test",
                        "width": 1254,
                        "height": 1254,
                    }
                ]
                result["caption"] = fields["caption"]
            else:
                result["text"] = fields.get("text", "")
            calls.append((method, dict(fields)))
            return web.json_response({"ok": True, "result": result})

        external = web.Application(client_max_size=12 * 1024 * 1024)
        external.router.add_post("/bot{token}/{method}", telegram)
        settings = BotSettings(
            rick_token=SecretStr("140001:TEST_ONLY_NOT_REAL"),
            morty_token=SecretStr("140002:TEST_ONLY_NOT_REAL"),
            media_token=SecretStr("140003:TEST_ONLY_NOT_REAL"),
            rick_webhook_secret=SecretStr("rick-secret-" * 4),
            morty_webhook_secret=SecretStr("morty-secret-" * 4),
            media_webhook_secret=SecretStr("media-secret-" * 4),
            service_key=portal.settings.security.service_key,
            admin_ids={OWNER},
            media_directory=portal.settings.media.directory,
        )
        api = create_app(
            portal.settings,
            providers=infrastructure_providers(portal.settings),
            middleware=[],
        )
        async with (
            api.router.lifespan_context(api),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=api),
                base_url="http://native-api",
            ) as client,
            TestServer(external) as external_server,
        ):
            runtime = MediaRuntime(settings, BackendClient(client, settings))
            runtime.bot.session.api = TelegramAPIServer.from_base(
                str(external_server.make_url(""))
            )
            app = web.Application()
            runtime.attach(app)
            try:
                async with TestClient(TestServer(app)) as gateway:
                    headers = {
                        "X-Telegram-Bot-Api-Secret-Token": "media-secret-" * 4
                    }
                    base = {
                        "message_id": 1,
                        "date": int(datetime.now(UTC).timestamp()),
                        "chat": {"id": USER, "type": "private"},
                        "from": {
                            "id": USER,
                            "is_bot": False,
                            "first_name": "Public user",
                        },
                    }
                    rejected = await gateway.post(
                        "/telegram/media",
                        json={
                            "update_id": 1,
                            "message": {**base, "text": "/start"},
                        },
                    )
                    assert rejected.status == 401 and not calls
                    response = await gateway.post(
                        "/telegram/media",
                        headers=headers,
                        json={
                            "update_id": 1,
                            "message": {
                                **base,
                                "text": "/start",
                                "entities": [
                                    {
                                        "type": "bot_command",
                                        "offset": 0,
                                        "length": 6,
                                    }
                                ],
                            },
                        },
                    )
                    assert response.status == 200
                    assert calls[0][0] == "sendPhoto"
                    menu = json.loads(calls[0][1]["reply_markup"])
                    assert (
                        menu["resize_keyboard"] and len(menu["keyboard"]) == 3
                    )
                    response = await gateway.post(
                        "/telegram/media",
                        headers=headers,
                        json={
                            "update_id": 2,
                            "message": {
                                **base,
                                "message_id": 2,
                                "text": "https://example.com/track.mp3",
                            },
                        },
                    )
                    assert response.status == 200
                    assert (
                        "🟩" in calls[-1][1]["text"]
                        or "⬜" in calls[-1][1]["text"]
                    )
                    async with portal.request() as request:
                        queries = await request.get(IMediaQueries)
                        jobs = await queries.page(USER, 1, 5)
                    assert jobs.total == 1 and jobs.items[0].status == "queued"
                    id = jobs.items[0].id
                    response = await gateway.post(
                        "/telegram/media",
                        headers=headers,
                        json={
                            "update_id": 3,
                            "message": {
                                **base,
                                "message_id": 3,
                                "text": f"/cancel {id}",
                                "entities": [
                                    {
                                        "type": "bot_command",
                                        "offset": 0,
                                        "length": 7,
                                    }
                                ],
                            },
                        },
                    )
                    assert response.status == 200
                    async with portal.request() as request:
                        queries = await request.get(IMediaQueries)
                        jobs = await queries.page(USER, 1, 5)
                    assert jobs.items[0].status == "cancelled"
                    assert "🛑" in calls[-1][1]["text"]
                    denied = await client.get(
                        f"/internal/media/jobs/{id}",
                        headers={
                            "Authorization": "Bearer "
                            + settings.service_key.get_secret_value(),
                            "X-Portal-Owner": str(USER + 1),
                        },
                    )
                    assert denied.status_code == 404
            finally:
                await runtime.bot.session.close()

    portal.run(workflow())
