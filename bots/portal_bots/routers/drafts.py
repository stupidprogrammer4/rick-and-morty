from datetime import UTC, datetime
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from portal_bots.app.voice import BotVoice
from portal_bots.interfaces import IBackendClient
from portal_contracts.content import DraftOut, DraftPage
from portal_contracts.enums import BotRole, Category

router = Router(name="drafts")


def draft_keyboard(id: int, revision: int, role: BotRole):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="تأیید",
                    callback_data=f"approve:{id}:{revision}:{role}",
                ),
                InlineKeyboardButton(
                    text="رد", callback_data=f"reject:{id}:{revision}:{role}"
                ),
            ]
        ]
    )


@router.message(Command("drafts"))
async def drafts(message: Message, backend: IBackendClient):
    if message.from_user is None:
        return
    words = (message.text or "").split()
    page = int(words[1]) if len(words) > 1 else 1
    raw = await backend.request(
        "GET", f"/drafts?page={page}", message.from_user.id
    )
    data = DraftPage.model_validate(raw)
    text = (
        "\n".join(
            f"#{draft.id} · نسخه {draft.revision} · {draft.status} · "
            f"{draft.title}"
            for draft in data.items
        )
        or "پیش‌نویسی نداریم."
    )
    await message.answer(escape(f"صفحه {page} · مجموع {data.total}\n{text}"))


@router.message(Command("draft", "approve", "reject", "publish", "schedule"))
async def draft_action(
    message: Message, backend: IBackendClient, role: BotRole
):
    if message.from_user is None:
        return
    words = (message.text or "").split()
    if len(words) < 2:
        await message.answer("شناسه پیش‌نویس را بعد از فرمان بده.")
        return
    id = int(words[1])
    raw = await backend.request("GET", f"/drafts/{id}", message.from_user.id)
    draft = DraftOut.model_validate(raw)
    action = words[0].split("@")[0][1:]
    if action in {"approve", "reject"}:
        revision = int(words[2]) if len(words) > 2 else draft.revision
        result = await backend.request(
            "POST",
            f"/drafts/{id}/{action}",
            message.from_user.id,
            data={"revision": revision, "origin_bot": role},
        )
        await message.answer(f"پیش‌نویس #{id}: {result['status']}")
        return
    if action in {"publish", "schedule"}:
        stamp = "now"
        if action == "schedule":
            if len(words) != 3:
                await message.answer(
                    "/schedule شناسه 2026-10-04T10:00:00+03:30"
                )
                return
            when = datetime.fromisoformat(words[2])
            if when.tzinfo is None:
                raise ValueError("زمان باید timezone داشته باشد.")
            stamp = str(int(when.timestamp()))
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="تأیید ارسال کانال",
                        callback_data=f"publish:{id}:{draft.revision}:{role}:{stamp}",
                    )
                ]
            ]
        )
    else:
        keyboard = draft_keyboard(id, draft.revision, role)
    await message.answer(
        escape(
            f"#{id} · نسخه {draft.revision}\n{draft.title}\n\n{draft.text}"
        ),
        reply_markup=keyboard,
    )


@router.callback_query()
async def decision(
    callback: CallbackQuery, backend: IBackendClient, role: BotRole
):
    words = (callback.data or "").split(":")
    if len(words) not in {4, 5} or words[0] not in {
        "approve",
        "reject",
        "publish",
    }:
        await callback.answer("کنترل نامعتبر است.")
        return
    action, id, revision, origin = words[:4]
    if origin != role:
        await callback.answer("این کنترل برای بات دیگری است.", show_alert=True)
        return
    data = {"revision": int(revision), "origin_bot": role.value}
    if action == "publish" and len(words) == 5 and words[4] != "now":
        data["scheduled_at"] = datetime.fromtimestamp(
            int(words[4]), UTC
        ).isoformat()
    result = await backend.request(
        "POST",
        f"/drafts/{int(id)}/{action}",
        callback.from_user.id,
        data=data,
    )
    await callback.answer("ثبت شد.")
    if isinstance(callback.message, Message):
        await callback.message.answer(escape(f"#{id}: {result['status']}"))


@router.message(Command("add_music", "add_tech", "notice"))
async def manual_draft(
    message: Message,
    backend: IBackendClient,
    role: BotRole,
    voice: BotVoice,
    update_id: int,
):
    if message.from_user is None:
        return
    command, _, text = (message.text or "").partition(" ")
    if not text.strip():
        await message.answer(
            "عنوان و متن را بعد از فرمان بنویس؛ خط اول عنوان است."
        )
        return
    category = {
        "/add_music": "music",
        "/add_tech": "tech",
        "/notice": "notice",
    }[command.split("@")[0]]
    title, _, body = text.partition("\n")
    raw = await backend.request(
        "POST",
        "/drafts",
        message.from_user.id,
        data={
            "category": category,
            "title": title[:160],
            "text": body or text,
            "publisher_bot": voice.presentation.posts[
                Category(category)
            ].publisher_bot.value,
        },
        headers={
            "X-Portal-Bot": role.value,
            "X-Idempotency-Key": str(update_id),
        },
    )
    await message.answer(
        escape(f"پیش‌نویس #{raw['id']}\n{raw['title']}\n{raw['text']}"),
        reply_markup=draft_keyboard(raw["id"], raw["revision"], role),
    )
