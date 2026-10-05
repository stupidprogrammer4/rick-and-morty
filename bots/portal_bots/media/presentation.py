from html import escape
from math import ceil

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from portal_contracts.media import MediaJobOut, MediaJobPage, MediaPresentation


def job_text(job: MediaJobOut, style: MediaPresentation) -> str:
    progress = min(10, int(job.sent * 10 / job.total)) if job.total else 0
    bar = "🟩" * progress + "⬜" * (10 - progress)
    percent = round(job.sent * 100 / job.total) if job.total else 0
    return (
        f"📥 <b>دانلود #{job.id}</b>\n"
        f"{style.separator}\n\n"
        f"{style.status_labels.get(job.status, escape(job.status))}\n\n"
        f"{bar} <b>{percent}٪</b>\n\n"
        f"📦 {job.total} فایل  ·  ✅ {job.sent} ارسال‌شده\n"
        f"⚠️ {job.failed} ناموفق یا نامشخص\n\n"
        f'<a href="{escape(job.url, quote=True)}">🔗 مشاهدهٔ لینک اصلی</a>'
    )


def job_keyboard(
    job: MediaJobOut, style: MediaPresentation
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=style.refresh_button,
                callback_data=f"media:status:{job.id}",
            ),
            InlineKeyboardButton(
                text=style.items_button,
                callback_data=f"media:items:{job.id}:1",
            ),
        ]
    ]
    if job.status in {"queued", "planning", "running"}:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=style.cancel_button,
                    callback_data=f"media:cancel:{job.id}",
                    style=style.button_styles.get("cancel"),
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text=style.back_button,
                callback_data="media:jobs:1",
                style=style.button_styles.get("back"),
            ),
            InlineKeyboardButton(
                text=style.home_button, callback_data="media:home"
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def jobs_text(page: MediaJobPage, style: MediaPresentation) -> str:
    entries = "\n\n".join(
        f"<b>#{job.id}</b> · "
        f"{style.status_labels.get(job.status, escape(job.status))}\n"
        f"📦 {job.sent}/{job.total} فایل  ·  ⚠️ {job.failed}"
        for job in page.items
    )
    return (
        f"{style.jobs_heading}\n{style.separator}\n\n"
        f"{entries or style.empty_jobs}\n\n"
        f"📄 {page.page} / {max(1, ceil(page.total / page.per_page))}"
    )


def jobs_keyboard(
    page: MediaJobPage, style: MediaPresentation
) -> InlineKeyboardMarkup:
    keyboard = page_keyboard(
        "media:jobs", page.page, page.per_page, page.total, style
    )
    entries = [
        [
            InlineKeyboardButton(
                text=f"📥 دانلود #{job.id} · {job.sent}/{job.total}",
                callback_data=f"media:status:{job.id}",
            )
        ]
        for job in page.items
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=entries + keyboard.inline_keyboard
    )


def main_keyboard(style: MediaPresentation) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=style.video_button,
                    style=style.button_styles.get("video"),
                ),
                KeyboardButton(
                    text=style.audio_button,
                    style=style.button_styles.get("audio"),
                ),
            ],
            [
                KeyboardButton(
                    text=style.jobs_button,
                    style=style.button_styles.get("jobs"),
                ),
                KeyboardButton(text=style.sources_button),
            ],
            [
                KeyboardButton(text=style.help_button),
                KeyboardButton(text=style.back_button),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="🔗 لینک رسانه یا پلی‌لیست…",
    )


def home_keyboard(style: MediaPresentation) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=style.video_button,
                    callback_data="media:video",
                    style=style.button_styles.get("video"),
                ),
                InlineKeyboardButton(
                    text=style.audio_button,
                    callback_data="media:audio",
                    style=style.button_styles.get("audio"),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=style.jobs_button,
                    callback_data="media:jobs:1",
                    style=style.button_styles.get("jobs"),
                ),
                InlineKeyboardButton(
                    text=style.sources_button, callback_data="media:sources"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=style.help_button, callback_data="media:help"
                )
            ],
        ]
    )


def navigation_keyboard(style: MediaPresentation) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=style.back_button,
                    callback_data="media:home",
                    style=style.button_styles.get("back"),
                ),
            ]
        ]
    )


def page_keyboard(
    prefix: str,
    page: int,
    per_page: int,
    total: int,
    style: MediaPresentation,
    back: str | None = None,
) -> InlineKeyboardMarkup:
    buttons = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text=style.previous_button,
                callback_data=f"{prefix}:{page - 1}",
            )
        )
    if page * per_page < total:
        buttons.append(
            InlineKeyboardButton(
                text=style.next_button, callback_data=f"{prefix}:{page + 1}"
            )
        )
    rows = [buttons] if buttons else []
    navigation = []
    if back:
        navigation.append(
            InlineKeyboardButton(
                text=style.back_button,
                callback_data=back,
                style=style.button_styles.get("back"),
            )
        )
    navigation.append(
        InlineKeyboardButton(
            text=style.home_button, callback_data="media:home"
        )
    )
    rows.append(navigation)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_screen(
    message: Message, text: str, keyboard: InlineKeyboardMarkup
) -> None:
    if text == message.html_text and keyboard == message.reply_markup:
        return
    try:
        if message.photo and len(text) > 1024:
            await message.answer(text, reply_markup=keyboard)
        elif message.photo:
            await message.edit_caption(caption=text, reply_markup=keyboard)
        else:
            await message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as exc:
        if "message is not modified" not in exc.message.lower():
            raise
