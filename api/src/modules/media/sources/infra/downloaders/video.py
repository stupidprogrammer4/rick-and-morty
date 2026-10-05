from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from src.modules.media.sources.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
)


class ExtractorLogger:
    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


class VideoDownloader:
    def __init__(self, request: DownloadProcessRequest):
        self.request = request

    def options(self) -> dict[str, Any]:
        return {
            "quiet": True,
            "no_warnings": True,
            "logger": ExtractorLogger(),
            "socket_timeout": self.request.policy.source_timeout_seconds,
            "retries": self.request.policy.source_retries,
            "extractor_retries": self.request.policy.source_retries,
            "fragment_retries": self.request.policy.source_retries,
            "cachedir": False,
            "cookiefile": self.request.cookie_file,
            "js_runtimes": {"deno": {}},
            "remote_components": [],
            "extractor_args": {},
            "noplaylist": True,
        }

    def plan(self) -> DownloadPlan:
        from yt_dlp import YoutubeDL

        options = self.options()
        options.update(
            extract_flat="in_playlist",
            skip_download=True,
            noplaylist=False,
            playlistend=self.request.policy.max_playlist_items + 1,
            lazy_playlist=True,
        )
        with YoutubeDL(cast(Any, options)) as downloader:
            info: Any = downloader.extract_info(
                self.request.url, download=False
            )
            if not info:
                raise ValueError("No public media found")
            entries = info.get("entries")
            rows = list(entries) if entries is not None else [info]
            if len(rows) > self.request.policy.max_playlist_items:
                raise ValueError(
                    "Playlist exceeds the configured item limit; "
                    "nothing was truncated"
                )
            items = []
            for row in rows:
                if row is None:
                    raise ValueError("Playlist contains inaccessible items")
                url = row.get("webpage_url") or row.get("url")
                if not url or not str(url).startswith("https://"):
                    if row.get("ie_key") == "Youtube" and row.get("id"):
                        url = "https://www.youtube.com/watch?v=" + row["id"]
                    else:
                        raise ValueError(
                            "Extractor did not return a public item URL"
                        )
                audio = (
                    self.request.mode == "audio"
                    or self.request.provider == "soundcloud"
                )
                items.append(
                    DownloadItem(
                        url=url,
                        source_url=url,
                        title=str(row.get("title") or "Media")[:200],
                        duration=row.get("duration"),
                        kind="audio" if audio else "video",
                    )
                )
        return DownloadPlan(items=items)

    def download(self, item: DownloadItem) -> DownloadedFile:
        from yt_dlp import YoutubeDL

        directory = Path(self.request.directory)
        prefix = uuid4().hex
        maximum = self.request.policy.max_file_bytes

        def progress(data: dict[str, Any]) -> None:
            if (
                data.get("downloaded_bytes", 0) > maximum
                or data.get("total_bytes", 0) > maximum
            ):
                raise ValueError("Media exceeds the Telegram file limit")
            if (
                sum(
                    path.stat().st_size
                    for path in directory.iterdir()
                    if path.is_file()
                )
                > maximum * 3
            ):
                raise ValueError("Download temporary size limit exceeded")

        def select_video(context: dict[str, Any]):
            formats = [
                candidate
                for candidate in context.get("formats", [])
                if candidate.get("vcodec") == "none"
                or min(
                    candidate.get("height") or float("inf"),
                    candidate.get("width") or float("inf"),
                )
                <= self.request.policy.video_height
            ]
            selector = downloader.build_format_selector(
                "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
            )
            return selector({**context, "formats": formats})

        options = self.options()
        audio = self.request.mode == "audio" or item.kind == "audio"
        options.update(
            outtmpl=str(directory / (prefix + ".%(ext)s")),
            max_filesize=maximum,
            progress_hooks=[progress],
            concurrent_fragment_downloads=1,
            restrictfilenames=True,
            merge_output_format="mp4",
            format="bestaudio/best" if audio else select_video,
            external_downloader="native",
            hls_prefer_native=True,
            postprocessors=[
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                }
            ]
            if audio
            else [],
            postprocessor_args={"ffmpeg": ["-threads", "1"]},
        )
        with YoutubeDL(cast(Any, options)) as downloader:
            info: Any = downloader.extract_info(item.url, download=False)
            if not info or info.get("is_live") or info.get("has_drm"):
                raise ValueError("Live or protected media is not supported")
            duration = info.get("duration")
            if (
                duration
                and duration > self.request.policy.max_duration_seconds
            ):
                raise ValueError("Media exceeds the configured duration limit")
            downloader.process_ie_result(info, download=True)
        files = [
            path
            for path in directory.glob(prefix + ".*")
            if path.suffix.lower()
            in {".mp4", ".mp3", ".m4a", ".webm", ".ogg", ".opus"}
        ]
        if len(files) != 1:
            raise ValueError(
                "Extractor did not produce one complete media file"
            )
        file = next(iter(files))
        if file.stat().st_size > maximum or file.stat().st_size == 0:
            raise ValueError(
                "Media exceeds the Telegram file limit or is empty"
            )
        return DownloadedFile(
            filename=file.name,
            kind="audio" if audio else "video",
            title=str(info.get("title") or item.title)[:200],
            performer=item.performer or info.get("artist"),
            source_url=info.get("webpage_url") or item.source_url,
        )
