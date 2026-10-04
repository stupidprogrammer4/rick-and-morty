from urllib.parse import urlsplit

from src.modules.media.sources.domain.dtos import (
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
)


class GalleryDownloader:
    def __init__(self, request: DownloadProcessRequest):
        self.request = request

    def plan(self) -> DownloadPlan:
        from gallery_dl import config, extractor
        from gallery_dl.extractor.message import Message

        config.clear()
        config.set(
            ("extractor",),
            "timeout",
            self.request.policy.source_timeout_seconds,
        )
        config.set(
            ("extractor",), "retries", self.request.policy.source_retries
        )
        config.set(
            ("extractor",),
            "sleep-request",
            self.request.policy.extractor_request_interval,
        )
        if self.request.cookie_file:
            config.set(
                ("extractor", "instagram"), "cookies", self.request.cookie_file
            )
        source = extractor.find(self.request.url)
        if source is None:
            raise ValueError("No gallery extractor found")
        items = []
        for message in source:
            if message[0] == Message.Queue:
                raise ValueError(
                    "Send an individual gallery/post URL rather than a profile"
                )
            if message[0] != Message.Url:
                continue
            _, url, metadata = message
            extension = str(
                metadata.get("extension")
                or urlsplit(url).path.rsplit(".", 1)[-1]
            ).lower()
            kind = "video" if extension in {"mp4", "webm"} else "photo"
            items.append(
                DownloadItem(
                    url=url,
                    source_url=self.request.url,
                    engine="direct",
                    kind=kind,
                    title=str(
                        metadata.get("description")
                        or metadata.get("title")
                        or f"Slide {len(items) + 1}"
                    )[:200],
                    headers={
                        "Referer": self.request.url,
                        "User-Agent": source.session.headers.get(
                            "User-Agent", self.request.policy.http_user_agent
                        ),
                    },
                )
            )
            if len(items) > self.request.policy.max_playlist_items:
                raise ValueError(
                    "Gallery exceeds configured item limit; "
                    "nothing was truncated"
                )
        if not items:
            raise ValueError(
                "No public images/videos found; a session may be required"
            )
        return DownloadPlan(items=items)
