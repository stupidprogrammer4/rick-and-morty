"""Persist media navigation settings without replacing custom labels."""

import json

import sqlalchemy as sa
from alembic import op

revision = "20261005_media_navigation"
down_revision = "20261005_youtube_api"
branch_labels = None
depends_on = None

DEFAULTS = {
    "back_button": "↩️ بازگشت",
    "home_button": "🏠 منوی اصلی",
    "refresh_button": "🔄 تازه\u200cسازی",
    "items_button": "📋 فایل\u200cها",
    "cancel_button": "🛑 لغو دانلود",
    "previous_button": "⬅️ قبلی",
    "next_button": "بعدی ➡️",
    "jobs_per_page": 5,
    "button_styles": {
        "video": "primary",
        "audio": "success",
        "jobs": "primary",
        "cancel": "danger",
        "back": "primary",
    },
    "help_text": (
        "💡 <b>دانلود در سه قدم</b>\n\n"
        "① 🎬 ویدئو و عکس یا 🎧 دانلود موزیک را انتخاب کن.\n"
        "② 🔗 لینک پست، آهنگ یا پلی‌لیست را بفرست.\n"
        "③ 📥 فایل‌ها به‌ترتیب همین‌جا می‌رسند.\n\n"
        "📦 از «دانلودهای من» وضعیت و فایل‌ها را ببین.\n"
        "↩️ بازگشت، انتخاب حالت دانلود را پاک می‌کند."
    ),
}


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT v.id, v.value FROM tbl_setting_values v "
            "JOIN tbl_setting_definitions d ON d.id = v.definition_id "
            "WHERE d.`key` = 'media.policy'"
        )
    ).all()
    for id, raw in rows:
        value = json.loads(raw)
        original = value.get("presentation", {})
        presentation = dict(original)
        for key, default in DEFAULTS.items():
            presentation.setdefault(key, default)
        hint = presentation.get("audio_hint", "")
        if hint == (
            "🎧 <b>وقت موزیکه!</b>\n\n"
            "🎵 لینک آهنگ، آلبوم یا پلی‌لیست را در پاسخ به همین پیام بفرست.\n"
            "📀 فایل‌ها جداگانه و قابل پخش در موزیک‌پلیر ارسال می‌شوند.\n"
            "✨ یا بنویس: /audio لینک"
        ):
            presentation["audio_hint"] = hint.replace(
                "را در پاسخ به همین پیام بفرست.", "را بفرست."
            )
        if presentation == original:
            continue
        value["presentation"] = presentation
        connection.execute(
            sa.text(
                "UPDATE tbl_setting_values SET value=:value, "
                "revision=revision+1, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=:id"
            ),
            {"id": id, "value": json.dumps(value, ensure_ascii=False)},
        )


def downgrade() -> None:
    pass
