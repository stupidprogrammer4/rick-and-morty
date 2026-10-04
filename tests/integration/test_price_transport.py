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
from portal_bots.runtime import BotRuntime
from src.config.providers import infrastructure_providers
from src.modules.content.publications.interfaces import (
    IPublicationChartCommands,
)
from tests.integration.conftest import OWNER
from tests.integration.test_publication_charts import (
    prepare_parent,
    read_publications,
)

pytestmark = pytest.mark.integration


class TelegramEndpoint:
    def __init__(self):
        self.messages = []
        self.photos = []
        self.edits = []
        self.answers = []

    async def handle(self, request):
        method = request.match_info["method"]
        fields = await request.post()
        if method == "getMe":
            id = int(request.match_info["token"].split(":")[0])
            result = {
                "id": id,
                "is_bot": True,
                "first_name": "Test bot",
                "username": f"test_{id}_bot",
            }
        elif method == "answerCallbackQuery":
            self.answers.append(dict(fields))
            result = True
        else:
            result = {
                "message_id": int(fields.get("message_id", 501)),
                "date": int(datetime.now(UTC).timestamp()),
                "chat": {"id": int(fields["chat_id"]), "type": "channel"},
            }
            if method == "sendPhoto":
                reference = fields["photo"]
                assert isinstance(reference, str)
                upload = fields[reference.removeprefix("attach://")]
                assert isinstance(upload, web.FileField)
                self.photos.append((upload.file.read(), dict(fields)))
                result["message_id"] = 501 + len(self.photos)
                result["photo"] = []
            elif method == "sendMessage":
                self.messages.append(dict(fields))
                result["text"] = fields["text"]
            elif method == "editMessageText":
                self.edits.append(dict(fields))
                result["text"] = fields["text"]
            else:
                raise AssertionError(f"Unexpected Telegram method: {method}")
        return web.json_response({"ok": True, "result": result})


def test_native_price_buttons_and_png_delivery_through_aiogram_and_api(portal):
    async def workflow():
        endpoint = TelegramEndpoint()
        telegram_app = web.Application()
        telegram_app.router.add_post("/bot{token}/{method}", endpoint.handle)
        settings = BotSettings(
            rick_token=SecretStr("140001:TEST_ONLY_NOT_REAL"),
            morty_token=SecretStr("140002:TEST_ONLY_NOT_REAL"),
            rick_webhook_secret=SecretStr("rick-test-key-" * 4),
            morty_webhook_secret=SecretStr("morty-test-key-" * 4),
            service_key=portal.settings.security.service_key,
            admin_ids={OWNER},
            api_url="http://native-api",
        )
        native_api = create_app(
            portal.settings,
            providers=infrastructure_providers(portal.settings),
            middleware=[],
        )
        async with native_api.router.lifespan_context(native_api):
            async with TestServer(telegram_app) as telegram:
                runtime = BotRuntime(settings)
                await runtime.client.aclose()
                runtime.client = httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=native_api),
                    trust_env=False,
                )
                runtime.backend = BackendClient(runtime.client, settings)
                for bot in runtime.bots.values():
                    bot.session.api = TelegramAPIServer.from_base(
                        str(telegram.make_url(""))
                    )
                async with TestClient(
                    TestServer(runtime.application())
                ) as client:
                    portal.settings.portal.gateway_url = str(
                        client.make_url("")
                    )
                    parent_id = await prepare_parent(portal)
                    parents, charts = await read_publications(portal)
                    message_id = next(
                        row for row in parents if row[0] == parent_id
                    )[2]
                    async with portal.request() as scope:
                        await (
                            await scope.get(IPublicationChartCommands)
                        ).dispatch(next(iter(charts))[0])
                    assert len(endpoint.messages) == 1
                    assert len(endpoint.photos) == 1
                    png, fields = endpoint.photos[0]
                    assert png.startswith(b"\x89PNG\r\n\x1a\n")
                    assert (
                        json.loads(fields["reply_parameters"])["message_id"]
                        == message_id
                    )
                    markup = json.loads(endpoint.messages[0]["reply_markup"])
                    assert (
                        markup["inline_keyboard"][0][-1]["callback_data"]
                        == f"prices:{parent_id}:1"
                    )

                    update = {
                        "update_id": 99,
                        "callback_query": {
                            "id": "test-price-page",
                            "from": {
                                "id": 420001,
                                "is_bot": False,
                                "first_name": "Reader",
                            },
                            "chat_instance": "test-channel",
                            "data": f"prices:{parent_id}:7",
                            "message": {
                                "message_id": message_id,
                                "date": 1,
                                "chat": {"id": -100140001, "type": "channel"},
                                "text": "Frozen report",
                            },
                        },
                    }
                    secret = {
                        "X-Telegram-Bot-Api-Secret-Token": (
                            settings.morty_webhook_secret.get_secret_value()
                        )
                    }
                    response = await client.post(
                        "/telegram/morty", json=update, headers=secret
                    )
                    assert response.status == 200
                    assert len(endpoint.edits) == 1
                    assert "اونس جهانی نقره" in endpoint.edits[0]["text"]
                    edited_markup = json.loads(
                        endpoint.edits[0]["reply_markup"]
                    )
                    assert (
                        "8/8"
                        in edited_markup["inline_keyboard"][0][-1]["text"]
                    )
                    assert endpoint.edits[0]["message_id"] == str(message_id)
                    update["callback_query"]["message"]["message_id"] = (
                        message_id + 1
                    )
                    response = await client.post(
                        "/telegram/morty", json=update, headers=secret
                    )
                    assert response.status == 200
                    assert len(endpoint.edits) == 1
                    assert endpoint.answers[-1]["show_alert"] == "true"
                    update["callback_query"]["data"] = "approve:1:1:morty"
                    response = await client.post(
                        "/telegram/morty", json=update, headers=secret
                    )
                    assert response.status == 200
                    assert len(endpoint.edits) == 1
                    assert endpoint.answers[-1]["show_alert"] == "true"

                    response = await client.post("/internal/photos", json={})
                    assert response.status == 401
                    response = await client.post(
                        "/internal/photos",
                        json={},
                        headers={
                            "Authorization": "Bearer "
                            + settings.service_key.get_secret_value()
                        },
                    )
                    assert response.status == 400
                    headers = {
                        "Authorization": "Bearer "
                        + settings.service_key.get_secret_value(),
                        "X-Portal-Owner": str(OWNER),
                    }
                    response = await runtime.client.get(
                        settings.api_url + "/internal/pricing/chart-cards",
                        headers=headers,
                    )
                    assert response.status_code == 200
                    cards = response.json()["data"]
                    assert len(cards) == 4 and all(
                        card["asset"]["id"] > 100000000 for card in cards
                    )
                    asset_id = cards[0]["asset"]["id"]
                    image_path = (
                        "/internal/pricing/chart-cards/" + f"{asset_id}/image"
                    )
                    response = await runtime.client.get(
                        settings.api_url + image_path,
                        headers=headers,
                    )
                    assert response.status_code == 200
                    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")

    portal.run(workflow())
