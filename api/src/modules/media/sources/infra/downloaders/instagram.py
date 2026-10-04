import json
import re
from urllib.parse import urlsplit

from yarl import URL

from src.modules.media.sources.domain.dtos import (
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.http import MediaHTTP


class InstagramDownloader:
    def __init__(self, request: DownloadProcessRequest):
        self.request = request

    async def plan(self) -> DownloadPlan:
        parts = urlsplit(self.request.url).path.strip("/").split("/")
        if len(parts) != 2 or parts[0] not in {"p", "reel", "reels", "tv"}:
            raise ValueError("Send an Instagram post or reel URL")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", parts[1]):
            raise ValueError("Invalid Instagram post identifier")
        http = MediaHTTP(self.request)
        async with http.session() as session:
            page = await http.metadata(session, "GET", self.request.url)
            token = re.search(
                r'\["LSD",\[\],\{"token":"([^"]+)"',
                page.decode(errors="replace"),
            )
            headers = {
                "Referer": self.request.url,
                "X-Requested-With": "XMLHttpRequest",
                "X-FB-Friendly-Name": (
                    "PolarisLoggedOutDesktopWWWPostRootContentQuery"
                ),
            }
            if token:
                headers["X-FB-LSD"] = token.group(1)
            csrf = session.cookie_jar.filter_cookies(
                URL(self.request.policy.instagram_query_url)
            ).get("csrftoken")
            if csrf:
                headers["X-CSRFToken"] = csrf.value
            raw = await http.metadata(
                session,
                "POST",
                self.request.policy.instagram_query_url,
                headers=headers,
                data={
                    "doc_id": self.request.policy.instagram_document_id,
                    "variables": json.dumps(
                        {"media_id": self.identifier(parts[1])}
                    ),
                    "fb_api_caller_class": "RelayModern",
                    "fb_api_req_friendly_name": (
                        "PolarisLoggedOutDesktopWWWPostRootContentQuery"
                    ),
                    "server_timestamps": "true",
                    "lsd": token.group(1) if token else "",
                },
            )
        data = json.loads(raw).get("data", {})
        media = data.get("xig_polaris_media") or {}
        product = media.get("if_not_gated_logged_out")
        if not isinstance(product, dict):
            raise ValueError(
                "Instagram did not expose this post for public download"
            )
        title = str((product.get("caption") or {}).get("text") or "Instagram")[
            :200
        ]
        rows = product.get("carousel_media") or [product]
        count = product.get("carousel_media_count", len(rows))
        if (
            count != len(rows)
            or not rows
            or len(rows) > self.request.policy.max_playlist_items
        ):
            raise ValueError(
                "Instagram returned an incomplete or oversized post"
            )
        return DownloadPlan(items=[self.item(row, title) for row in rows])

    def identifier(self, shortcode: str) -> str:
        alphabet = (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        )
        result = 0
        for character in shortcode:
            result = result * 64 + alphabet.index(character)
        return str(result)

    def item(self, row: dict, title: str) -> DownloadItem:
        videos = row.get("video_versions") or []
        if videos:
            allowed = [
                v
                for v in videos
                if v.get("height", 0) <= self.request.policy.video_height
            ]
            media = max(allowed or videos, key=lambda v: v.get("width", 0))
            kind = "video"
        else:
            images = row.get("image_versions2", {}).get("candidates", [])
            if not images:
                raise ValueError(
                    "Instagram did not expose a file for every slide"
                )
            media = max(
                images, key=lambda v: v.get("width", 0) * v.get("height", 0)
            )
            kind = "photo"
        return DownloadItem(
            url=media["url"],
            source_url=self.request.url,
            title=title,
            kind=kind,
            engine="direct",
            headers={"Referer": self.request.url},
        )
