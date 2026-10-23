from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery, Chat, Message

from portal_bots.routers.pages import chart_page
from portal_contracts.enums import BotRole
from portal_contracts.telegram import PublishedChartPage
from src.modules.content.publications.app.charts import gallery_navigation


@pytest.mark.asyncio
async def test_chart_callback_edits_same_photo_without_sending_another():
    navigation = gallery_navigation(12, 44, 1, 3)
    result = PublishedChartPage(
        caption="Page two", png_base64="iVBORw0KGgo=", navigation=navigation
    )
    backend = SimpleNamespace(
        request=AsyncMock(return_value=result.model_dump())
    )
    bot = AsyncMock()
    message = Message(
        message_id=99,
        date=datetime.now(UTC),
        chat=Chat(id=-100123, type="channel"),
    ).as_(bot)
    callback = CallbackQuery(
        id="query",
        from_user={"id": 123, "is_bot": False, "first_name": "Reader"},
        chat_instance="instance",
        data="charts:44:1",
        message=message,
    ).as_(bot)
    await chart_page(callback, backend, BotRole.MORTY, 123)
    assert bot.await_count == 2
    answer, edit = [call.args[0] for call in bot.await_args_list]
    assert answer.__api_method__ == "answerCallbackQuery"
    assert edit.__api_method__ == "editMessageMedia"
    assert edit.message_id == 99 and edit.chat_id == -100123
    assert edit.media.caption == "Page two"
    buttons = edit.reply_markup.inline_keyboard[0]
    assert [button.callback_data for button in buttons] == [
        "charts:44:0",
        "charts:44:1",
        "charts:44:2",
    ]
    backend.request.assert_awaited_once_with(
        "GET",
        "/publications/charts/44/pages/1?role=morty&chat_id=-100123&message_id=99",
        123,
        timeout=35,
    )


@pytest.mark.asyncio
async def test_public_chart_navigation_bypasses_private_admin_settings():
    from portal_bots.routers.auth import PrivateAdminMiddleware
    from portal_bots.routers.presentation import PresentationMiddleware

    callback = CallbackQuery(
        id="public",
        from_user={"id": 555, "is_bot": False, "first_name": "Reader"},
        chat_instance="channel",
        data="charts:44:1",
        message=Message(
            message_id=99,
            date=datetime.now(UTC),
            chat=Chat(id=-100123, type="channel"),
        ),
    )
    settings = SimpleNamespace(admin_ids={123})
    handler = AsyncMock(return_value="ok")
    assert (
        await PrivateAdminMiddleware(settings)(handler, callback, {}) == "ok"
    )
    assert await PresentationMiddleware()(handler, callback, {}) == "ok"
    assert handler.await_count == 2


@pytest.mark.asyncio
async def test_expired_chart_click_is_acknowledged_without_backend_work():
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import AnswerCallbackQuery

    bot = AsyncMock(
        side_effect=TelegramBadRequest(
            method=AnswerCallbackQuery(callback_query_id="expired"),
            message=(
                "query is too old and response timeout expired "
                "or query ID is invalid"
            ),
        )
    )
    callback = CallbackQuery(
        id="expired",
        from_user={"id": 555, "is_bot": False, "first_name": "Reader"},
        chat_instance="channel",
        data="charts:44:1",
        message=Message(
            message_id=99,
            date=datetime.now(UTC),
            chat=Chat(id=-100123, type="channel"),
        ),
    ).as_(bot)
    backend = SimpleNamespace(request=AsyncMock())
    await chart_page(callback, backend, BotRole.MORTY, 123)
    backend.request.assert_not_awaited()
