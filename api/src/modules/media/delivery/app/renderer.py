from html import escape

from src.modules.media.delivery.domain.dtos import MediaCaption


class MediaCaptionRenderer:
    def render(self, data: MediaCaption) -> str:
        source = escape(data.source_url, quote=True)
        caption = (
            f"🦋 <b>{escape(data.title[:150])}</b>\n"
            f"📦 {data.position} / {data.total} · #{data.job_id}\n"
            f'🔗 <a href="{source}">منبع فایل</a>'
        )
        if data.provider == "spotify":
            caption += (
                "\n🎵 تطبیق با Spotify؛ فایل از منبع لینک‌شده تهیه شده است."
            )
        return caption
