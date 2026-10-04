import json
import re
from urllib.parse import urlsplit

import aiohttp

from src.modules.media.sources.domain.dtos import (
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.http import MediaHTTP


class PinterestDownloader:
    def __init__(self, request: DownloadProcessRequest):
        self.request = request

    async def plan(self) -> DownloadPlan:
        http = MediaHTTP(self.request)
        url = self.request.url
        async with http.session() as client:
            if urlsplit(url).hostname == "pin.it":
                http.validate(url)
                async with client.get(url, max_redirects=6) as response:
                    if response.status != 200:
                        raise ValueError(
                            f"Pinterest short link: HTTP {response.status}"
                        )
                    url = str(response.url)
            parsed = urlsplit(url)
            if not parsed.hostname or not (
                parsed.hostname == "pinterest.com"
                or parsed.hostname.endswith(".pinterest.com")
            ):
                raise ValueError(
                    "Pinterest link must resolve to a Pinterest pin"
                )
            parts = parsed.path.strip("/").split("/")
            if len(parts) != 2 or parts[0] != "pin" or not parts[1].isdigit():
                raise ValueError("Send an individual Pinterest pin URL")
            try:
                page = await http.metadata(client, "GET", url)
                pin = self.page_pin(page, parts[1])
            except ValueError:
                pin = None
            if pin is None:
                pin = await self.api_pin(http, client, parts[1], url)
        items = self.items(pin, url)
        if not items or len(items) > self.request.policy.max_playlist_items:
            raise ValueError(
                "Pinterest pin is empty or exceeds the item limit"
            )
        return DownloadPlan(items=items)

    def page_pin(self, page: bytes, identifier: str) -> dict | None:
        text = page.decode(errors="replace")
        decoder = json.JSONDecoder()
        candidates = []
        for match in re.finditer(
            r"__PWS_RELAY_REGISTER_COMPLETED_REQUEST__\(", text
        ):
            try:
                _, end = decoder.raw_decode(text[match.end() :])
                payload, _ = decoder.raw_decode(
                    text[match.end() + end :].lstrip(", ")
                )
            except ValueError:
                continue
            pin = (
                payload.get("data", {}).get("v3GetPinQueryv2", {}).get("data")
            )
            if (
                isinstance(pin, dict)
                and str(pin.get("entityId")) == identifier
            ):
                candidates.append(pin)
        if not candidates:
            return None
        return max(candidates, key=self.media_score)

    def media_score(self, pin: dict) -> int:
        media = (
            pin.get("storyPinData")
            or pin.get("videos")
            or pin.get("images_orig")
        )
        encoded = json.dumps(media)
        return encoded.count("https://") + encoded.count(".mp4") * 10

    async def api_pin(
        self,
        http: MediaHTTP,
        client: aiohttp.ClientSession,
        identifier: str,
        url: str,
    ) -> dict:
        raw = await http.metadata(
            client,
            "GET",
            self.request.policy.pinterest_api_url,
            params={
                "source_url": urlsplit(url).path,
                "data": json.dumps(
                    {
                        "options": {
                            "id": identifier,
                            "field_set_key": "detailed",
                        },
                        "context": {},
                    }
                ),
            },
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": url},
        )
        pin = json.loads(raw).get("resource_response", {}).get("data")
        if not isinstance(pin, dict) or str(pin.get("id")) != identifier:
            raise ValueError("Pinterest did not return the requested pin")
        return pin

    def items(self, pin: dict, source: str) -> list[DownloadItem]:
        title = str(pin.get("title") or pin.get("description") or "Pinterest")[
            :200
        ]
        story = pin.get("story_pin_data") or pin.get("storyPinData")
        if story:
            media = [
                block
                for page in story.get("pages", [])
                for block in page.get("blocks", [])
                if block.get("type")
                in {
                    "story_pin_image_block",
                    "story_pin_video_block",
                    "story_pin_music_block",
                }
                or block.get("__typename")
                in {
                    "StoryPinImageBlock",
                    "StoryPinVideoBlock",
                    "StoryPinMusicBlock",
                }
            ]
            return [self.block(block, source, title) for block in media]
        carousel = pin.get("carousel_data") or pin.get("carouselData")
        if carousel:
            return [
                self.image(slot.get("images", {}), source, title)
                for slot in carousel.get(
                    "carousel_slots", carousel.get("carouselSlots", [])
                )
            ]
        if pin.get("videos"):
            return [self.video(pin["videos"], source, title)]
        if pin.get("isVideo") or pin.get("storyPinDataId"):
            raise ValueError("Pinterest did not expose every media file")
        images = pin.get("images", {}) or {"orig": pin.get("images_orig")}
        return [self.image(images, source, title)]

    def block(self, block: dict, source: str, title: str) -> DownloadItem:
        video = block.get("video") or block.get("videoDataV2")
        if video:
            return self.video(video, source, title)
        if block.get("audio"):
            return DownloadItem(
                url=block["audio"]["audio_url"],
                source_url=source,
                title=title,
                kind="audio",
                engine="direct",
            )
        images = block.get("image", {}).get("images", {})
        if not images:
            images = {
                key.removeprefix("images_"): value
                for key, value in block.items()
                if key.startswith("images_")
                and isinstance(value, dict)
                and value.get("url")
            }
        return self.image(images, source, title)

    def image(self, images: dict, source: str, title: str) -> DownloadItem:
        media = images.get("orig") or images.get("originals")
        if not media:
            available = [
                image
                for image in images.values()
                if isinstance(image, dict) and image.get("url")
            ]
            if not available:
                raise ValueError("Pinterest did not expose every image")
            media = max(
                available,
                key=lambda image: (
                    image.get("width", 0) * image.get("height", 0)
                ),
            )
        return DownloadItem(
            url=media["url"],
            source_url=source,
            title=title,
            kind="photo",
            engine="direct",
        )

    def video(self, videos: dict, source: str, title: str) -> DownloadItem:
        formats = [
            value
            for key, group in videos.items()
            if key
            in {"video_list", "videoList", "videoList720P", "videoListMobile"}
            for value in group.values()
            if value.get("url")
        ]
        files = [
            f
            for f in formats
            if urlsplit(f.get("url", "")).path.endswith(".mp4")
        ]
        if files:
            allowed = [
                f
                for f in files
                if f.get("height", 0) <= self.request.policy.video_height
            ]
            media = max(allowed or files, key=lambda f: f.get("width", 0))
            return DownloadItem(
                url=media["url"],
                source_url=source,
                title=title,
                kind="video",
                engine="direct",
            )
        manifests = [
            f
            for f in formats
            if urlsplit(f.get("url", "")).path.endswith(".m3u8")
        ]
        if not manifests:
            raise ValueError("Pinterest did not expose a downloadable video")
        return DownloadItem(
            url=manifests[0]["url"],
            source_url=source,
            title=title,
            kind="video",
            engine="video",
        )
