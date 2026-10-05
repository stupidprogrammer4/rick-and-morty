from html import escape
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InaccessibleMessage,
    Message,
)

from portal_bots.interfaces import IBackendClient
from portal_bots.media.presentation import (
    home_keyboard,
    job_keyboard,
    job_text,
    jobs_keyboard,
    jobs_text,
    main_keyboard,
    navigation_keyboard,
    page_keyboard,
    show_screen,
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
        message: Message,
        backend: IBackendClient,
        media_policy: MediaPolicy,
        state: FSMContext,
        command: CommandObject,
    ):
        if message.chat.type != "private":
            return
        await state.clear()
        if command.command == "help":
            await message.answer(
                media_policy.presentation.help_text,
                reply_markup=navigation_keyboard(media_policy.presentation),
            )
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
        message: Message,
        backend: IBackendClient,
        media_policy: MediaPolicy,
        state: FSMContext,
    ):
        if message.chat.type != "private":
            return
        await state.clear()
        raw = await backend.request(
            "GET",
            f"/media/jobs?page=1&per_page={media_policy.presentation.jobs_per_page}",
            message.chat.id,
        )
        page = MediaJobPage.model_validate(raw)
        await message.answer(
            jobs_text(page, media_policy.presentation),
            reply_markup=jobs_keyboard(page, media_policy.presentation),
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
            reply_markup=job_keyboard(job, media_policy.presentation),
        )

    @router.callback_query(F.data.startswith("media:"))
    async def callback(
        query: CallbackQuery,
        state: FSMContext,
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
        style = media_policy.presentation
        if query.data in {
            "media:home",
            "media:help",
            "media:sources",
            "media:video",
            "media:audio",
        }:
            await query.answer()
            if query.data in {"media:video", "media:audio"}:
                audio = query.data == "media:audio"
                await state.set_data({"mode": "audio" if audio else "media"})
                text = style.audio_hint if audio else style.video_hint
                keyboard = navigation_keyboard(style)
            else:
                await state.clear()
                text = (
                    media_policy.welcome
                    if query.data == "media:home"
                    else style.help_text
                    if query.data == "media:help"
                    else style.sources_text
                )
                keyboard = (
                    home_keyboard(style)
                    if query.data == "media:home"
                    else navigation_keyboard(style)
                )
            await show_screen(query.message, text, keyboard)
            return
        parts = (query.data or "").split(":")
        if len(parts) not in {3, 4} or not parts[2].isdecimal():
            await query.answer()
            return
        id = int(parts[2])
        owner = query.from_user.id
        if parts[1] == "jobs":
            raw = await backend.request(
                "GET",
                f"/media/jobs?page={id}&per_page={style.jobs_per_page}",
                owner,
            )
            page = MediaJobPage.model_validate(raw)
            text, keyboard = (
                jobs_text(page, media_policy.presentation),
                jobs_keyboard(page, style),
            )
        elif parts[1] == "items" and len(parts) == 4 and parts[3].isdecimal():
            raw = await backend.request(
                "GET",
                f"/media/jobs/{id}/items?page={parts[3]}&per_page={style.jobs_per_page}",
                owner,
            )
            items = MediaItemPage.model_validate(raw)
            labels = media_policy.presentation.status_labels
            text = f"📦 <b>فایل‌های درخواست #{id}</b>\n\n" + "\n\n".join(
                f"{item.position}. {escape(item.title[:100])}\n"
                f"{escape(labels.get(item.status, item.status))}"
                for item in items.items
            )
            keyboard = page_keyboard(
                f"media:items:{id}",
                items.page,
                items.per_page,
                items.total,
                style,
                f"media:status:{id}",
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
                job_keyboard(job, style),
            )
        else:
            await query.answer()
            return
        await query.answer()
        await show_screen(query.message, text, keyboard)

    @router.message(F.text)
    async def download(
        message: Message,
        backend: IBackendClient,
        update_id: int,
        state: FSMContext,
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
        if text in {style.back_button, style.home_button}:
            await state.clear()
            await message.answer(
                media_policy.welcome, reply_markup=main_keyboard(style)
            )
            return
        if text in {style.video_button, style.audio_button}:
            await state.set_data(
                {"mode": "audio" if text == style.audio_button else "media"}
            )
            await message.answer(
                style.audio_hint
                if text == style.audio_button
                else style.video_hint,
                reply_markup=navigation_keyboard(style),
            )
            return
        if text == style.sources_button:
            await state.clear()
            await message.answer(
                style.sources_text, reply_markup=navigation_keyboard(style)
            )
            return
        if text == style.help_button:
            await state.clear()
            await message.answer(
                style.help_text, reply_markup=navigation_keyboard(style)
            )
            return
        if text == style.jobs_button:
            await state.clear()
            raw = await backend.request(
                "GET",
                f"/media/jobs?page=1&per_page={style.jobs_per_page}",
                message.chat.id,
            )
            page = MediaJobPage.model_validate(raw)
            await message.answer(
                jobs_text(page, style),
                reply_markup=jobs_keyboard(page, style),
            )
            return
        explicit_audio = text.startswith("/audio ")
        selection = await state.get_data()
        audio = explicit_audio or selection.get("mode") == "audio"
        url = text.split(maxsplit=1)[1].strip() if explicit_audio else text
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
            reply_markup=job_keyboard(accepted.job, style),
        )

    return router
