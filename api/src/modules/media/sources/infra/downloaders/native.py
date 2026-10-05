from pathlib import Path

from mutagen.id3 import APIC, TALB, TIT2, TPE1, TRCK
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover

from src.modules.media.sources.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.http import MediaHTTP
from src.modules.media.sources.infra.threads import MediaMetadataThreads


class NativeMediaMetadata:
    def __init__(
        self, request: DownloadProcessRequest, threads: MediaMetadataThreads
    ):
        self.request = request
        self.threads = threads

    async def cover(self, item: DownloadItem) -> bytes | None:
        if not item.cover_url:
            return None
        http = MediaHTTP(self.request)
        try:
            async with http.session() as session:
                result = await http.metadata(session, "GET", item.cover_url)
            if len(result) <= 1_000_000 and (
                result.startswith(b"\xff\xd8\xff")
                or result.startswith(b"\x89PNG\r\n\x1a\n")
            ):
                return result
        except Exception:
            pass
        return None

    def inspect(
        self, path: Path, item: DownloadItem, artwork: bytes | None
    ) -> None:
        if path.suffix == ".mp3":
            media = MP3(path)
        elif path.suffix in {".m4a", ".mp4"}:
            media = MP4(path)
        else:
            raise ValueError("Native transfer requires MP3, M4A or MP4")
        if (
            not media.info.length
            or media.info.length > self.request.policy.max_duration_seconds
        ):
            raise ValueError(
                "Missing duration or configured duration limit exceeded"
            )
        if item.duration and abs(media.info.length - item.duration) > max(
            3, item.duration * self.request.policy.music_duration_tolerance
        ):
            raise ValueError(
                "Downloaded file duration differs from source metadata"
            )
        if item.kind == "audio":
            if media.tags is None:
                media.add_tags()
            if isinstance(media, MP3):
                tags = media.tags
                if tags is None:
                    raise ValueError("Unable to initialize audio tags")
                tags.add(TIT2(encoding=3, text=item.title))
                if item.performer:
                    tags.add(TPE1(encoding=3, text=item.performer))
                if item.album:
                    tags.add(TALB(encoding=3, text=item.album))
                if item.track_number:
                    tags.add(TRCK(encoding=3, text=str(item.track_number)))
                if artwork:
                    tags.add(
                        APIC(
                            encoding=3,
                            mime="image/png"
                            if artwork.startswith(b"\x89PNG")
                            else "image/jpeg",
                            type=3,
                            desc="Cover",
                            data=artwork,
                        )
                    )
            else:
                media["\xa9nam"] = [item.title]
                if item.performer:
                    media["\xa9ART"] = [item.performer]
                if item.album:
                    media["\xa9alb"] = [item.album]
                if item.track_number:
                    media["trkn"] = [(item.track_number, 0)]
                if artwork:
                    media["covr"] = [
                        MP4Cover(
                            artwork,
                            imageformat=MP4Cover.FORMAT_PNG
                            if artwork.startswith(b"\x89PNG")
                            else MP4Cover.FORMAT_JPEG,
                        )
                    ]
            media.save()
        if path.stat().st_size > self.request.policy.max_file_bytes:
            raise ValueError("Media exceeds the Telegram file limit")

    async def finish(
        self, path: Path, item: DownloadItem, kind: str
    ) -> DownloadedFile:
        artwork = await self.cover(item)
        await self.threads.run(self.inspect, path, item, artwork)
        return DownloadedFile(
            filename=path.name,
            kind="audio" if item.kind == "audio" else "video",
            title=item.title,
            source_url=item.source_url,
            performer=item.performer,
        )
