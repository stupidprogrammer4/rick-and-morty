from datetime import datetime
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator


class MediaPresentation(BaseModel):
    show_avatar: bool = True
    video_button: str = "🎬 ویدئو و عکس"
    audio_button: str = "🎧 دانلود موزیک"
    jobs_button: str = "📦 دانلودهای من"
    sources_button: str = "🌐 منابع و امکانات"
    help_button: str = "💡 راهنما"
    video_hint: str = (
        "🎬 <b>بیا یک دانلود تازه شروع کنیم!</b>\n\n"
        "🔗 لینک ویدئو، ریلز، عکس یا پست اسلایدی را بفرست.\n"
        "🖼 تمام اسلایدهای پست به‌ترتیب ارسال می‌شوند.\n"
        "✨ لینک پلی‌لیست هم می‌تونی بفرستی!"
    )
    audio_hint: str = (
        "🎧 <b>وقت موزیکه!</b>\n\n"
        "🎵 لینک آهنگ، آلبوم یا پلی‌لیست را در پاسخ به همین پیام بفرست.\n"
        "📀 فایل‌ها جداگانه و قابل پخش در موزیک‌پلیر ارسال می‌شوند.\n"
        "✨ یا بنویس: /audio لینک"
    )
    sources_text: str = (
        "🌍 <b>دنیای رسانه در یک بات</b>\n"
        "━━━━━━ 🦋 ━━━━━━\n\n"
        "📸 <b>Instagram</b> · عکس، ریلز و اسلایدهای پست\n"
        "▶️ <b>YouTube</b> · ویدئو، صوت و پلی‌لیست\n"
        "☁️ <b>SoundCloud</b> · آهنگ و پلی‌لیست\n"
        "🟢 <b>Spotify</b> · آهنگ، آلبوم و پلی‌لیست با تطبیق منبع صوت\n"
        "🎭 <b>سایت‌های بیشتر</b> · TikTok، Vimeo و منابع دیگر\n\n"
        "🔗 لینک رسانه یا صفحهٔ عمومی را بفرست؛ بررسیش می‌کنم.\n"
        "🔐 بعضی منابع نیازمند ورود یا session هستند.\n"
        "📦 سقف اندازه و تعداد فایل‌ها برای همه اعمال می‌شود."
    )
    jobs_heading: str = "📦 <b>گالری دانلودهای من</b>"
    empty_jobs: str = "✨ اینجا هنوز خالیه! یک لینک بفرست تا شروع کنیم."
    separator: str = "━━━━━━ 🦋 ━━━━━━"
    status_labels: dict[str, str] = {
        "queued": "⏳ در صف دانلود",
        "planning": "🔎 در حال شناسایی رسانه‌ها",
        "running": "🚀 در حال دانلود و ارسال",
        "completed": "✅ همهٔ فایل‌ها ارسال شدند",
        "partial": "🟡 دانلود با چند مورد ناموفق پایان یافت",
        "failed": "⚠️ دانلود انجام نشد",
        "cancelled": "🛑 درخواست لغو شد",
        "sent": "✅ ارسال‌شده",
        "unknown": "❔ وضعیت ارسال نامشخص",
        "downloading": "📥 در حال دانلود",
        "sending": "📤 در حال ارسال",
    }


class MediaPolicy(BaseModel):
    presentation: MediaPresentation = Field(default_factory=MediaPresentation)
    enabled: bool = True
    providers: set[str] = {
        "youtube",
        "instagram",
        "soundcloud",
        "spotify",
        "gallery",
        "video",
        "browser",
        "direct",
    }
    max_file_bytes: int = Field(
        default=49_000_000, ge=1_000_000, le=50_000_000
    )
    max_playlist_items: int = Field(default=500, ge=1, le=5000)
    max_duration_seconds: int = Field(default=3600, ge=30, le=14400)
    item_timeout_seconds: int = Field(default=240, ge=30, le=900)
    active_per_user: int = Field(default=2, ge=1, le=10)
    active_global: int = Field(default=30, ge=1, le=200)
    requests_per_hour: int = Field(default=10, ge=1, le=100)
    disk_budget_bytes: int = Field(default=600_000_000, ge=100_000_000)
    disk_reserve_bytes: int = Field(default=2_000_000_000, ge=500_000_000)
    orphan_age_seconds: int = Field(default=3600, ge=1800, le=86400)
    browser_enabled: bool = True
    video_height: int = Field(default=720, ge=144, le=1080)
    welcome: str = (
        "🦋 <b>به AMU Downloader خوش اومدی!</b>\n"
        "━━━━━━ ✨ ━━━━━━\n\n"
        "🎬 ویدئوهای دوست‌داشتنی\n🎧 موزیک و پلی‌لیست\n"
        "📸 عکس‌ها و تمام اسلایدهای پست\n\n"
        "🔗 فقط لینک را بفرست؛ بقیه‌اش با من!\n"
        "📦 فایل‌ها به‌ترتیب برات ارسال می‌شوند.\n"
        "🧹 بعد از ارسال، فایل‌های موقت خودکار پاک می‌شوند.\n\n"
        "👇 از دکمه‌های پایین هم می‌تونی شروع کنی."
    )


class MediaCreate(BaseModel):
    owner_id: int = Field(gt=0)
    chat_id: int = Field(gt=0)
    bot_id: int = Field(gt=0)
    update_id: int = Field(ge=0)
    url: str = Field(min_length=8, max_length=2048)
    mode: Literal["media", "audio"] = "media"

    @model_validator(mode="after")
    def private_link(self) -> Self:
        parsed = urlsplit(self.url)
        if self.chat_id != self.owner_id:
            raise ValueError("Downloads belong to the requesting private chat")
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in {None, 443}
        ):
            raise ValueError("Send a public HTTPS media link")
        return self


class MediaJobOut(BaseModel):
    id: int
    owner_id: int
    url: str
    mode: str
    provider: str
    status: str
    total: int
    sent: int
    failed: int
    error: str | None
    created_at: datetime


class MediaAccepted(BaseModel):
    job: MediaJobOut
    duplicate: bool = False


class MediaJobPage(BaseModel):
    items: list[MediaJobOut]
    total: int
    page: int
    per_page: int


class MediaItemOut(BaseModel):
    id: int
    job_id: int
    position: int
    title: str
    status: str
    source_url: str
    error: str | None
    message_id: int | None


class MediaItemPage(BaseModel):
    items: list[MediaItemOut]
    total: int
    page: int
    per_page: int


class MediaFileDelivery(BaseModel):
    job_id: int
    item_id: int
    owner_id: int = Field(gt=0)
    filename: str = Field(
        pattern=r"^[0-9a-f]{32}\.(mp4|mp3|m4a|webm|ogg|opus|jpg|jpeg|png|webp|gif|pdf)$"
    )
    kind: Literal["audio", "video", "photo", "document"]
    caption: str = Field(max_length=4096)
    title: str = Field(max_length=200)
    performer: str | None = Field(default=None, max_length=200)


class MediaFileResult(BaseModel):
    status: Literal["sent", "failed", "unknown", "rate_limited"]
    message_id: int | None = None
    file_id: str | None = None
    retry_after: int | None = None
    reason: str | None = None


class MediaFileAuthorization(BaseModel):
    authorized: bool
