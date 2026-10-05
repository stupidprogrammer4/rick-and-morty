import re
from time import monotonic
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

import httpx

from src.config.settings import PortalAppSettings
from src.modules.media.sources.domain.dtos import (
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
)
from src.modules.media.sources.domain.music import (
    MusicCandidate,
    ResolvedMedia,
)
from src.modules.media.sources.infra.threads import MediaMetadataThreads


class MetadataDeadline:
    def __init__(self, seconds: int):
        self.deadline = monotonic() + seconds

    def debug(self, message: str) -> None:
        self.check()

    def warning(self, message: str) -> None:
        self.check()

    def error(self, message: str) -> None:
        self.check()

    def check(self) -> None:
        if monotonic() >= self.deadline:
            raise TimeoutError("Media metadata deadline exceeded")


class MediaMetadataExtraction:
    def __init__(
        self,
        threads: MediaMetadataThreads,
        settings: PortalAppSettings,
        client: httpx.AsyncClient,
    ):
        self.threads = threads
        self.settings = settings
        self.client = client

    def options(self, request: DownloadProcessRequest) -> dict[str, Any]:
        options = {
            "quiet": True,
            "no_warnings": True,
            "logger": MetadataDeadline(request.policy.source_timeout_seconds),
            "socket_timeout": request.policy.source_timeout_seconds,
            "retries": request.policy.source_retries,
            "extractor_retries": request.policy.source_retries,
            "cachedir": False,
            "js_runtimes": {},
            "remote_components": [],
            "skip_download": True,
            "format": "bestaudio/best",
            "proxy": self.settings.media.youtube_proxy_url.get_secret_value()
            if request.provider == "youtube"
            else "",
            "extractor_args": {
                "youtube": {
                    "player_client": request.policy.youtube_clients,
                    "player_skip": ["webpage", "configs"],
                }
            },
        }
        if request.youtube_po_token:
            options["extractor_args"]["youtube"]["po_token"] = [
                "mweb.gvs+" + request.youtube_po_token
            ]
        return options

    async def token(
        self, request: DownloadProcessRequest, url: str
    ) -> DownloadProcessRequest:
        provider_url = self.settings.media.youtube_token_provider_url
        if not provider_url or self.validate(url) != "youtube":
            return request
        identifier = parse_qs(urlsplit(self.youtube_url(url)).query)["v"][0]
        response = await self.client.post(
            provider_url.rstrip("/") + "/get_pot",
            json={
                "content_binding": identifier,
                "proxy": (
                    self.settings.media.youtube_proxy_url.get_secret_value()
                    or None
                ),
            },
            timeout=request.policy.source_timeout_seconds,
        )
        response.raise_for_status()
        if len(response.content) > 16000:
            raise ValueError("YouTube token response exceeds its size limit")
        token = response.json().get("poToken")
        if not isinstance(token, str) or not token or len(token) > 12000:
            raise ValueError(
                "YouTube token provider returned an invalid token"
            )
        return request.model_copy(update={"youtube_po_token": token})

    def validate(self, url: str) -> str:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("Invalid public source URL")
        if parsed.port not in {None, 443}:
            raise ValueError("Invalid public source port")
        if host in {
            "youtu.be",
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
        }:
            return "youtube"
        if host in {
            "soundcloud.com",
            "www.soundcloud.com",
            "api.soundcloud.com",
            "api-v2.soundcloud.com",
        }:
            return "soundcloud"
        raise ValueError("Unsupported media metadata source")

    def youtube_url(self, url: str, collection: bool = False) -> str:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if collection and (playlist := query.get("list", [""])[0]):
            if not re.fullmatch(r"[A-Za-z0-9_-]{2,100}", playlist):
                raise ValueError("Invalid YouTube playlist ID")
            return "https://www.youtube.com/playlist?list=" + playlist
        video = (
            parsed.path.strip("/")
            if parsed.hostname == "youtu.be"
            else query.get("v", [""])[0]
            if parsed.path == "/watch"
            else parsed.path.split("/")[-1]
            if parsed.path.startswith(("/shorts/", "/embed/", "/live/"))
            else ""
        )
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
            raise ValueError("Send a YouTube video or playlist URL")
        return "https://www.youtube.com/watch?v=" + video

    def extract(
        self, request: DownloadProcessRequest, url: str, flat: bool
    ) -> Any:
        from yt_dlp import YoutubeDL

        options = self.options(request)
        options.update(
            extract_flat="in_playlist" if flat else False,
            noplaylist=not flat,
            playlistend=request.policy.max_playlist_items + 1,
            lazy_playlist=True,
        )
        with YoutubeDL(cast(Any, options)) as downloader:
            result: Any = downloader.extract_info(url, download=False)
            if result and "entries" in result:
                result["entries"] = list(result["entries"])
        if not result:
            raise ValueError("No public source metadata found")
        return result

    def collection(self, request: DownloadProcessRequest) -> DownloadPlan:
        self.validate(request.url)
        url = self.youtube_url(request.url, collection=True)
        info = self.extract(request, url, True)
        rows = list(info["entries"]) if "entries" in info else [info]
        if not rows or len(rows) > request.policy.max_playlist_items:
            raise ValueError(
                "Empty or oversized collection; nothing was truncated"
            )
        items = []
        for row in rows:
            if not row:
                raise ValueError("Collection contains an inaccessible item")
            url = row.get("webpage_url") or row.get("url")
            if not url or not str(url).startswith("https://"):
                if re.fullmatch(r"[A-Za-z0-9_-]{11}", str(row.get("id", ""))):
                    url = "https://www.youtube.com/watch?v=" + row["id"]
                else:
                    raise ValueError("Collection item URL is unavailable")
            self.validate(url)
            items.append(
                DownloadItem(
                    url=url,
                    source_url=url,
                    engine="youtube",
                    title=str(row.get("title") or "Media")[:200],
                    performer=row.get("artist") or row.get("uploader"),
                    duration=row.get("duration"),
                    kind="audio" if request.mode == "audio" else "video",
                )
            )
        return DownloadPlan(items=items)

    async def plan(self, request: DownloadProcessRequest) -> DownloadPlan:
        if request.policy.youtube_api_url and "list" not in parse_qs(
            urlsplit(request.url).query
        ):
            self.validate(request.url)
            url = self.youtube_url(request.url)
            return DownloadPlan(
                items=[
                    DownloadItem(
                        url=url,
                        source_url=url,
                        engine="youtube",
                        kind="audio" if request.mode == "audio" else "video",
                    )
                ]
            )
        selected = request
        if "list" not in parse_qs(urlsplit(request.url).query):
            selected = await self.token(request, request.url)
        result = await self.threads.run(self.collection, selected)
        return result

    def candidates(
        self, request: DownloadProcessRequest, source: str, query: str
    ) -> list[MusicCandidate]:
        prefix = "scsearch" if source == "soundcloud" else "ytsearch"
        info = self.extract(
            request,
            prefix + str(request.policy.music_search_results) + ":" + query,
            True,
        )
        rows = list(info.get("entries") or [])
        result = []
        for row in rows:
            if not row:
                continue
            url = row.get("webpage_url") or row.get("url")
            if not str(url).startswith("https://"):
                continue
            self.validate(url)
            result.append(
                MusicCandidate(
                    url=url,
                    title=str(row.get("title") or "")[:200],
                    performer=row.get("artist") or row.get("uploader"),
                    duration=row.get("duration"),
                    isrc=row.get("isrc"),
                )
            )
        return result

    async def search(
        self, request: DownloadProcessRequest, source: str, query: str
    ) -> list[MusicCandidate]:
        selected = request.model_copy(update={"provider": source})
        result = await self.threads.run(
            self.candidates, selected, source, query
        )
        return result

    def media(
        self, request: DownloadProcessRequest, item: DownloadItem
    ) -> ResolvedMedia:
        provider = self.validate(item.url)
        if provider == "soundcloud":
            from yt_dlp.extractor.soundcloud import SoundcloudIE

            if not SoundcloudIE.suitable(item.url):
                raise ValueError("Send a public SoundCloud track URL")
        request = request.model_copy(update={"provider": provider})
        url = self.youtube_url(item.url) if provider == "youtube" else item.url
        info = self.extract(request, url, False)
        duration = float(info.get("duration") or 0)
        if info.get("is_live") or info.get("has_drm"):
            raise ValueError(
                "Source does not expose a downloadable public file"
            )
        if not duration or duration > request.policy.max_duration_seconds:
            raise ValueError(
                "Missing duration or configured duration limit exceeded"
            )
        audio = item.kind == "audio" or request.mode == "audio"
        choices = [
            row
            for row in info.get("formats") or []
            if str(row.get("url", "")).startswith("https://")
            and (
                row.get("protocol") in {"http", "https"}
                or (
                    provider == "soundcloud"
                    and audio
                    and row.get("protocol") == "m3u8_native"
                    and row.get("ext") == "mp3"
                )
            )
            and not row.get("has_drm")
            and "preview" not in str(row.get("format_id", ""))
            and (
                not row.get("filesize")
                or row["filesize"] <= request.policy.max_file_bytes
            )
            and (
                row.get("vcodec") == "none"
                and row.get("ext") in {"m4a", "mp3"}
                if audio
                else row.get("ext") == "mp4"
                and row.get("vcodec") not in {None, "none"}
                and row.get("acodec") not in {None, "none"}
                and min(
                    row.get("height") or float("inf"),
                    row.get("width") or float("inf"),
                )
                <= request.policy.video_height
            )
        ]
        if not choices:
            raise ValueError(
                "Source has no compatible direct file without codec processes"
            )
        selected = max(
            choices,
            key=lambda row: (
                row.get("protocol") in {"http", "https"},
                row.get("abr") or row.get("height") or 0,
                row.get("tbr") or 0,
            ),
        )
        return ResolvedMedia(
            duration=duration,
            source=MusicCandidate(
                url=info.get("webpage_url") or item.source_url,
                title=str(info.get("title") or "")[:200],
                performer=info.get("artist") or info.get("uploader"),
                duration=duration,
                isrc=info.get("isrc"),
            ),
            item=item.model_copy(
                update={
                    "url": selected["url"],
                    "source_url": info.get("webpage_url") or item.source_url,
                    "engine": "direct",
                    "kind": "audio" if audio else "video",
                    "duration": duration,
                    "transport": "hls_mp3"
                    if selected.get("protocol") == "m3u8_native"
                    else "direct",
                    "headers": {
                        key: value
                        for key, value in (
                            info.get("http_headers") or {}
                        ).items()
                        if key.lower() in {"user-agent", "referer", "origin"}
                    },
                }
            ),
        )

    async def resolve(
        self, request: DownloadProcessRequest, item: DownloadItem
    ) -> ResolvedMedia:
        selected = await self.token(request, item.url)
        result = await self.threads.run(self.media, selected, item)
        return result
