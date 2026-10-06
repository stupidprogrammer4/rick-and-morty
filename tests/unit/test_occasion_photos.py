import base64
import json

import httpx
import pytest
from aiogram.client.telegram import TelegramAPIServer
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pydantic import SecretStr, ValidationError

from portal_bots.config.settings import BotSettings
from portal_bots.infra.backend import BackendClient
from portal_bots.runtime import BotRuntime
from portal_contracts.telegram import TelegramDelivery
from src.modules.content.occasions.app.photo import occasion_photo


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,photo_error,text_error,status,photo_count,text_count",
    [
        ("<b>امروز</b>\nمورتی، تفنگ پورتال رو بده.", None, None, "sent", 1, 0),
        ("x" * 1024, None, None, "sent", 1, 0),
        ("x" * 1025, None, None, "sent", 1, 1),
        ("🤯" * 513, None, None, "sent", 1, 1),
        ("x" * 1025, None, 429, "unknown", 1, 0),
        ("x" * 1025, None, 400, "unknown", 1, 0),
        ("short", 429, None, "rate_limited", 0, 0),
        ("short", 400, None, "failed", 0, 0),
    ],
    ids=[
        "caption",
        "caption-limit",
        "long-text",
        "emoji-limit",
        "partial-rate-limit",
        "partial-bad-request",
        "photo-rate-limit",
        "photo-bad-request",
    ],
)
async def test_occasion_photo_delivery_with_native_aiogram(
    snapshot,
    monkeypatch,
    text,
    photo_error,
    text_error,
    status,
    photo_count,
    text_count,
):
    # These transport cases do not consume updates or attach shared routers.
    monkeypatch.setattr(
        "portal_bots.runtime.Dispatcher.include_routers", lambda *args: None
    )
    photos, messages = [], []

    async def telegram(request):
        method = request.match_info["method"]
        fields = await request.post()
        if method == "getMe":
            identity = int(request.match_info["token"].split(":")[0])
            result = {"id": identity, "is_bot": True, "first_name": "Test"}
            return web.json_response({"ok": True, "result": result})
        error = photo_error if method == "sendPhoto" else text_error
        if error:
            return web.json_response(
                {
                    "ok": False,
                    "error_code": error,
                    "description": "test failure",
                    "parameters": {"retry_after": 3} if error == 429 else {},
                },
                status=error,
            )
        result = {
            "message_id": 501 if method == "sendPhoto" else 502,
            "date": 1,
            "chat": {"id": -100140001, "type": "channel"},
        }
        if method == "sendPhoto":
            reference = fields["photo"]
            assert isinstance(reference, str)
            upload = fields[reference.removeprefix("attach://")]
            assert isinstance(upload, web.FileField)
            assert upload.file.read() == base64.b64decode(occasion_photo())
            photos.append(dict(fields))
            result["photo"] = []
        elif method == "sendMessage":
            messages.append(dict(fields))
            result["text"] = fields["text"]
        else:
            raise AssertionError(method)
        return web.json_response({"ok": True, "result": result})

    def backend(request):
        assert request.url.path == "/internal/configuration/bot"
        return httpx.Response(
            200,
            json={
                "data": {
                    "channel_id": -100140001,
                    "presentation": snapshot[1].model_dump(mode="json"),
                }
            },
        )

    settings = BotSettings(
        rick_token=SecretStr("140001:TEST_ONLY_NOT_REAL"),
        morty_token=SecretStr("140002:TEST_ONLY_NOT_REAL"),
        rick_webhook_secret=SecretStr("rick-test-key-" * 4),
        morty_webhook_secret=SecretStr("morty-test-key-" * 4),
        service_key=SecretStr("test-service-key-" * 4),
        admin_ids={140001},
    )
    app = web.Application()
    app.router.add_post("/bot{token}/{method}", telegram)
    async with TestServer(app) as server:
        runtime = BotRuntime(settings)
        await runtime.client.aclose()
        runtime.client = httpx.AsyncClient(
            transport=httpx.MockTransport(backend)
        )
        runtime.backend = BackendClient(runtime.client, settings)
        for bot in runtime.bots.values():
            bot.session.api = TelegramAPIServer.from_base(
                str(server.make_url("/")).rstrip("/")
            )
        async with TestClient(TestServer(runtime.application())) as client:
            body = TelegramDelivery(
                role="rick",
                chat_id=-100140001,
                publication_id=1,
                text=text,
                png_base64=occasion_photo(),
            ).model_dump(mode="json")
            response = await client.post("/internal/messages", json=body)
            assert response.status == 401
            assert photos == messages == []
            headers = {
                "Authorization": "Bearer "
                + settings.service_key.get_secret_value()
            }
            response = await client.post(
                "/internal/messages", json=body, headers=headers
            )
            assert response.status == 200
            outcome = await response.json()
            assert outcome["status"] == status
            if status in ("sent", "unknown"):
                assert outcome["message_id"] == 501
            if status == "unknown":
                assert outcome["retry_after"] is None
                assert outcome["reason"] == "photo_text_delivery_incomplete"
            assert len(photos) == photo_count
            assert len(messages) == text_count
            if photos:
                if len(text.encode("utf-16-le")) // 2 <= 1024:
                    assert photos[0]["caption"] == text
                    assert photos[0]["parse_mode"] == "HTML"
                else:
                    assert not photos[0].get("caption")
            if messages:
                assert messages[0]["text"] == text
                assert (
                    json.loads(messages[0]["reply_parameters"])["message_id"]
                    == 501
                )
            body["chat_id"] = -100999999
            response = await client.post(
                "/internal/messages", json=body, headers=headers
            )
            assert response.status == 403
            body["png_base64"] = "invalid"
            response = await client.post(
                "/internal/messages", json=body, headers=headers
            )
            assert response.status == 400


@pytest.mark.parametrize(
    "image",
    [
        base64.b64encode(b"not a png").decode(),
        base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x" * (256 * 1024)).decode(),
    ],
)
def test_post_photo_rejects_invalid_or_oversized_images(image):
    with pytest.raises(ValidationError):
        TelegramDelivery(
            role="rick",
            chat_id=-100140001,
            publication_id=1,
            text="test",
            png_base64=image,
        )
