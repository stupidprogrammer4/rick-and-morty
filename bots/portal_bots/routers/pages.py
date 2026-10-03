from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message

from portal_bots.app.pages import page_keyboard
from portal_bots.interfaces import IBackendClient
from portal_contracts.content import PublishedPage
from portal_contracts.enums import BotRole

router = Router(name="published price pages")


@router.callback_query(F.data.regexp(r"^prices:[1-9][0-9]*:[0-9]+$"))
async def page(
    callback: CallbackQuery,
    backend: IBackendClient,
    role: BotRole,
    portal_admin_id: int,
):
    if not isinstance(callback.message, Message) or callback.data is None:
        await callback.answer()
        return
    _, publication, index = callback.data.split(":")
    message = callback.message
    raw = await backend.request(
        "GET",
        f"/publications/{int(publication)}/pages/{int(index)}"
        f"?role={role.value}&chat_id={message.chat.id}&message_id={message.message_id}",
        portal_admin_id,
    )
    result = PublishedPage.model_validate(raw)
    try:
        await message.edit_text(
            result.text,
            reply_markup=page_keyboard(result.navigation),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in exc.message:
            raise
    await callback.answer()
