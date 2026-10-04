from html import escape
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    ForceReply,
    FSInputFile,
    InaccessibleMessage,
    Message,
)

from portal_bots.interfaces import IBackendClient
from portal_bots.media.presentation import (
    job_keyboard,
    job_text,
    jobs_text,
    main_keyboard,
    page_keyboard,
)
from portal_contracts.media import (
    MediaAccepted,
    MediaCreate,
    MediaItemPage,
    MediaJobOut,
    MediaJobPage,
    MediaPolicy,
)


def make_router() -> Router:
    router = Router(name="public-media")

    @router.message(Command("start", "help"))
    async def welcome(
        message: Message, backend: IBackendClient, media_policy: MediaPolicy
    ):
        if message.chat.type != "private":
            return
        if media_policy.presentation.show_avatar:
            await message.answer_photo(
                FSInputFile(Path(__file__).parent / "assets" / "avatar.png"),
                caption=media_policy.welcome,
                reply_markup=main_keyboard(media_policy.presentation),
            )
        else:
            await message.answer(
                media_policy.welcome,
                reply_markup=main_keyboard(media_policy.presentation),
            )

    @router.message(Command("jobs"))
    async def jobs(
        message: Message, backend: IBackendClient, media_policy: MediaPolicy
    ):
        if message.chat.type != "private":
            return
        raw = await backend.request(
            "GET", "/media/jobs?page=1", message.chat.id
        )
        page = MediaJobPage.model_validate(raw)
        await message.answer(
            jobs_text(page, media_policy.presentation),
            reply_markup=page_keyboard(
                "media:jobs", page.page, page.per_page, page.total
            ),
        )

    @router.message(Command("status", "cancel"))
    async def operation(
        message: Message,
        command: CommandObject,
        backend: IBackendClient,
        media_policy: MediaPolicy,
    ):
        if message.chat.type != "private":
            return
        if not command.args or not command.args.strip().isdecimal():
            await message.answer("📋 شمارهٔ درخواست را بنویس؛ مثلاً /status 12")
            return
        id = int(command.args)
        path = f"/media/jobs/{id}" + (
            "/cancel" if command.command == "cancel" else ""
        )
        raw = await backend.request(
            "POST" if command.command == "cancel" else "GET",
            path,
            message.chat.id,
        )
        job = MediaJobOut.model_validate(raw)
        await message.answer(
            job_text(job, media_policy.presentation),
            reply_markup=job_keyboard(job),
        )

    @router.callback_query(F.data.startswith("media:"))
    async def callback(
        query: CallbackQuery,
        backend: IBackendClient,
        media_policy: MediaPolicy,
    ):
        if (
            query.message is None
            or isinstance(query.message, InaccessibleMessage)
            or query.message.chat.type != "private"
            or query.from_user.id != query.message.chat.id
        ):
            await query.answer("دسترسی مجاز نیست.", show_alert=True)
            return
        parts = (query.data or "").split(":")
        if len(parts) not in {3, 4} or not parts[2].isdecimal():
            await query.answer()
            return
        id = int(parts[2])
        owner = query.from_user.id
        if parts[1] == "jobs":
            raw = await backend.request("GET", f"/media/jobs?page={id}", owner)
            page = MediaJobPage.model_validate(raw)
            text, keyboard = (
                jobs_text(page, media_policy.presentation),
                page_keyboard(
                    "media:jobs", page.page, page.per_page, page.total
                ),
            )
        elif parts[1] == "items" and len(parts) == 4 and parts[3].isdecimal():
            raw = await backend.request(
                "GET", f"/media/jobs/{id}/items?page={parts[3]}", owner
            )
            items = MediaItemPage.model_validate(raw)
            labels = media_policy.presentation.status_labels
            text = f"📦 <b>فایل‌های درخواست #{id}</b>\n\n" + "\n\n".join(
                f"{item.position}. {escape(item.title[:100])}\n"
                f"{escape(labels.get(item.status, item.status))}"
                for item in items.items
            )
            keyboard = page_keyboard(
                f"media:items:{id}", items.page, items.per_page, items.total
            )
        elif parts[1] in {"status", "cancel"}:
            raw = await backend.request(
                "POST" if parts[1] == "cancel" else "GET",
                f"/media/jobs/{id}"
                + ("/cancel" if parts[1] == "cancel" else ""),
                owner,
            )
            job = MediaJobOut.model_validate(raw)
            text, keyboard = (
                job_text(job, media_policy.presentation),
                job_keyboard(job),
            )
        else:
            await query.answer()
            return
        await query.answer()
        if (
            text != query.message.html_text
            or keyboard != query.message.reply_markup
        ):
            await query.message.edit_text(text, reply_markup=keyboard)

    @router.message(F.text)
    async def download(
        message: Message,
        backend: IBackendClient,
        update_id: int,
        media_policy: MediaPolicy,
    ):
        if (
            message.chat.type != "private"
            or message.from_user is None
            or message.from_user.id != message.chat.id
        ):
            return
        text = (message.text or "").strip()
        style = media_policy.presentation
        if text in {style.video_button, style.audio_button}:
            await message.answer(
                style.audio_hint
                if text == style.audio_button
                else style.video_hint,
                reply_markup=ForceReply(
                    selective=True,
                    input_field_placeholder="🔗 لینک را اینجا بفرست…",
                ),
            )
            return
        if text == style.sources_button:
            await message.answer(
                style.sources_text, reply_markup=main_keyboard(style)
            )
            return
        if text == style.help_button:
            await message.answer(
                media_policy.welcome, reply_markup=main_keyboard(style)
            )
            return
        if text == style.jobs_button:
            raw = await backend.request(
                "GET", "/media/jobs?page=1", message.chat.id
            )
            page = MediaJobPage.model_validate(raw)
            await message.answer(
                jobs_text(page, style),
                reply_markup=page_keyboard(
                    "media:jobs", page.page, page.per_page, page.total
                ),
            )
            return
        audio = text.startswith("/audio ")
        url = text.split(maxsplit=1)[1].strip() if audio else text
        bot = message.bot
        if bot is None:
            return
        reply = message.reply_to_message
        if (
            reply is not None
            and reply.from_user is not None
            and reply.from_user.id == bot.id
            and reply.html_text == style.audio_hint
        ):
            audio = True
        try:
            data = MediaCreate(
                owner_id=message.from_user.id,
                chat_id=message.chat.id,
                bot_id=bot.id,
                update_id=update_id,
                url=url,
                mode="audio" if audio else "media",
            )
        except ValueError:
            await message.answer(
                "🔗 یک لینک HTTPS بفرست.\n🎧 برای دانلود صدا: /audio لینک"
            )
            return
        raw = await backend.request(
            "POST", "/media/jobs", data.owner_id, data=data.model_dump()
        )
        accepted = MediaAccepted.model_validate(raw)
        await message.answer(
            job_text(accepted.job, media_policy.presentation),
            reply_markup=job_keyboard(accepted.job),
        )

    return router
