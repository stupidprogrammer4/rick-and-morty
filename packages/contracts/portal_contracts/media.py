from datetime import datetime
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_serializer, model_validator

MediaExtractor = Literal[
    "video",
    "gallery",
    "browser",
    "direct",
    "spotify",
    "instagram",
    "pinterest",
]


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
        "📌 <b>Pinterest</b> · عکس، ویدئو و اسلایدهای پین\n"
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
        "reserved": "🚀 نوبت دانلود رسید",
        "ready": "✅ آمادهٔ ارسال",
    }


class MediaPolicy(BaseModel):
    presentation: MediaPresentation = Field(default_factory=MediaPresentation)
    enabled: bool = True
    providers: set[str] = {
        "youtube",
        "instagram",
        "soundcloud",
        "spotify",
        "pinterest",
        "gallery",
        "video",
        "browser",
        "direct",
    }
    source_routes: dict[str, list[MediaExtractor]] = Field(
        default_factory=lambda: {
            "instagram.reel": ["instagram", "video"],
            "instagram": ["instagram", "gallery"],
            "pinterest": ["pinterest"],
            "youtube": ["video"],
            "soundcloud": ["video"],
            "spotify": ["spotify"],
            "video": ["video", "gallery", "browser"],
        }
    )
    pinterest_api_url: str = (
        "https://www.pinterest.com/resource/PinResource/get/"
    )
    instagram_query_url: str = "https://www.instagram.com/api/graphql"
    instagram_document_id: str = "27130156389949648"
    max_file_bytes: int = Field(
        default=49_000_000, ge=1_000_000, le=50_000_000
    )
    max_playlist_items: int = Field(default=500, ge=1, le=5000)
    max_duration_seconds: int = Field(default=3600, ge=30, le=14400)
    item_timeout_seconds: int = Field(default=240, ge=30, le=900)
    concurrent_downloads: int = Field(default=2, ge=1, le=4)
    concurrent_plans: int = Field(default=1, ge=1, le=2)
    buffered_items: int = Field(default=4, ge=1, le=12)
    source_timeout_seconds: int = Field(default=10, ge=5, le=60)
    source_retries: int = Field(default=0, ge=0, le=3)
    extractor_request_interval: float = Field(default=0, ge=0, le=30)
    http_user_agent: str = Field(
        default="AMU-Downloader/1.0 (+https://github.com/stupidprogrammer4/rick-and-morty)",
        min_length=8,
        max_length=250,
        pattern=r"^[^\r\n]+$",
    )
    active_per_user: int = Field(default=2, ge=1, le=10)
    active_global: int = Field(default=30, ge=1, le=200)
    requests_per_hour: int = Field(default=10, ge=1, le=100)
    disk_budget_bytes: int = Field(default=600_000_000, ge=100_000_000)
    disk_reserve_bytes: int = Field(default=2_000_000_000, ge=500_000_000)
    orphan_age_seconds: int = Field(default=3600, ge=1800, le=86400)
    browser_enabled: bool = True
    video_height: int = Field(default=720, ge=144, le=1080)
    youtube_clients: list[str] = Field(
        default_factory=lambda: ["mweb", "web_safari", "android_vr"],
        min_length=1,
        max_length=4,
    )
    music_sources: list[Literal["soundcloud", "youtube"]] = Field(
        default_factory=lambda: ["soundcloud", "youtube"],
        min_length=1,
        max_length=2,
    )
    music_search_results: int = Field(default=5, ge=1, le=10)
    music_match_threshold: float = Field(default=0.8, ge=0.5, le=1)
    music_duration_tolerance: float = Field(default=0.08, ge=0.01, le=0.2)
    file_cache_seconds: int = Field(default=604800, ge=0, le=2592000)
    hls_max_segments: int = Field(default=512, ge=1, le=2048)
    hls_segment_concurrency: int = Field(default=2, ge=1, le=4)
    spotify_auth_url: str = "https://accounts.spotify.com/api/token"
    spotify_api_url: str = "https://api.spotify.com/v1"
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

    @field_serializer("providers")
    def ordered_providers(self, value: set[str]) -> list[str]:
        return sorted(value)


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
    file_id: str | None = Field(default=None, min_length=1, max_length=512)


class MediaFileResult(BaseModel):
    status: Literal["sent", "failed", "unknown", "rate_limited", "cache_miss"]
    message_id: int | None = None
    file_id: str | None = None
    retry_after: int | None = None
    reason: str | None = None


class MediaFileAuthorization(BaseModel):
    authorized: bool
