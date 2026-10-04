from html import escape

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from portal_contracts.media import MediaJobOut, MediaJobPage, MediaPresentation


def job_text(job: MediaJobOut, style: MediaPresentation) -> str:
    progress = min(10, int(job.sent * 10 / job.total)) if job.total else 0
    bar = "🟩" * progress + "⬜" * (10 - progress)
    percent = round(job.sent * 100 / job.total) if job.total else 0
    return (
        f"🦋 <b>درخواست #{job.id}</b>\n"
        f"{style.separator}\n"
        f"{style.status_labels.get(job.status, escape(job.status))}\n\n"
        f"{bar} {percent}٪\n\n"
        f"📦 تعداد فایل‌ها: {job.total}\n✅ ارسال‌شده: {job.sent}\n"
        f"⚠️ ناموفق/نامشخص: {job.failed}\n"
        f'<a href="{escape(job.url, quote=True)}">🔗 لینک اصلی</a>'
    )


def job_keyboard(job: MediaJobOut) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="🔄 به‌روزرسانی", callback_data=f"media:status:{job.id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 فایل‌ها", callback_data=f"media:items:{job.id}:1"
            )
        ],
    ]
    if job.status in {"queued", "planning", "running"}:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🛑 لغو", callback_data=f"media:cancel:{job.id}"
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def jobs_text(page: MediaJobPage, style: MediaPresentation) -> str:
    return (
        style.jobs_heading
        + "\n\n"
        + (
            "\n\n".join(job_text(job, style) for job in page.items)
            if page.items
            else style.empty_jobs
        )
        + f"\n\n📄 صفحه {page.page}"
    )


def main_keyboard(style: MediaPresentation) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=style.video_button),
                KeyboardButton(text=style.audio_button),
            ],
            [
                KeyboardButton(text=style.jobs_button),
                KeyboardButton(text=style.sources_button),
            ],
            [KeyboardButton(text=style.help_button)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="🔗 لینک رسانه یا پلی‌لیست…",
    )


def page_keyboard(
    prefix: str, page: int, per_page: int, total: int
) -> InlineKeyboardMarkup:
    buttons = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️ قبلی", callback_data=f"{prefix}:{page - 1}"
            )
        )
    if page * per_page < total:
        buttons.append(
            InlineKeyboardButton(
                text="بعدی ➡️", callback_data=f"{prefix}:{page + 1}"
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [])
