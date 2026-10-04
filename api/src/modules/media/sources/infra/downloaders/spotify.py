import json
import os
from typing import Any
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from src.modules.media.sources.domain.dtos import (
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.video import (
    ExtractorLogger,
    VideoDownloader,
)


class SpotifyDownloader:
    def __init__(self, request: DownloadProcessRequest):
        self.request = request

    def plan(self) -> DownloadPlan:
        parts = urlsplit(self.request.url).path.strip("/").split("/")
        if (
            len(parts) != 2
            or parts[0] not in {"track", "album", "playlist"}
            or not parts[1].isalnum()
        ):
            raise ValueError("Send a Spotify track, album or playlist URL")
        if os.getenv("SPOTIPY_CLIENT_ID") and os.getenv(
            "SPOTIPY_CLIENT_SECRET"
        ):
            return self.official(parts[0], parts[1])
        with httpx.Client(
            trust_env=False,
            timeout=self.request.policy.source_timeout_seconds,
            headers={"User-Agent": self.request.policy.http_user_agent},
        ) as client:
            response = client.get(
                "https://open.spotify.com/embed/" + "/".join(parts)
            )
            response.raise_for_status()
        document = BeautifulSoup(response.text, "html.parser")
        node = document.find("script", id="__NEXT_DATA__")
        if node is None:
            raise ValueError(
                "Spotify metadata requires a session "
                "or configured API credentials"
            )
        state = (
            json.loads(node.get_text())
            .get("props", {})
            .get("pageProps", {})
            .get("state", {})
        )
        entity = state.get("data", {}).get("entity")
        if not entity:
            raise ValueError(
                "Spotify did not expose collection metadata; "
                "a session or API credentials are required"
            )
        rows = entity.get("trackList")
        if rows is None:
            rows = [entity] if parts[0] == "track" else []
        total = entity.get("totalTracks") or entity.get("total") or len(rows)
        if (
            parts[0] == "playlist"
            and not entity.get("totalTracks")
            and not entity.get("total")
        ):
            raise ValueError(
                "Spotify did not expose the full playlist count; "
                "API credentials are required to verify completeness"
            )
        if total > len(rows):
            raise ValueError(
                "Spotify embedded page is incomplete; "
                "API credentials are needed for the full playlist"
            )
        items = []
        for row in rows:
            uri = row.get("uri") or row.get("id")
            if not uri or not str(uri).startswith("spotify:track:"):
                raise ValueError("Spotify page contains an unavailable track")
            url = "https://open.spotify.com/track/" + uri.rsplit(":", 1)[-1]
            artist = row.get("subtitle") or ", ".join(
                a.get("name", "") for a in row.get("artists", [])
            )
            items.append(
                DownloadItem(
                    url=url,
                    source_url=url,
                    title=str(row.get("title") or row.get("name") or "Track")[
                        :200
                    ],
                    performer=artist[:200],
                    duration=(row.get("duration") or 0) / 1000 or None,
                    kind="audio",
                    engine="spotify",
                )
            )
        if not items or len(items) > self.request.policy.max_playlist_items:
            raise ValueError("Empty or oversized Spotify collection")
        return DownloadPlan(items=items)

    def official(self, kind: str, id: str) -> DownloadPlan:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials

        client = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(),
            requests_timeout=self.request.policy.source_timeout_seconds,
            retries=self.request.policy.source_retries,
        )
        rows: list[dict[str, Any]] = []
        if kind == "track":
            track = client.track(id)
            if track is None:
                raise ValueError("Spotify track unavailable")
            rows = [track]
        else:
            page = (
                client.playlist_items(id)
                if kind == "playlist"
                else client.album_tracks(id)
            )
            while page:
                rows.extend(
                    (row.get("track") or row.get("item") or row)
                    for row in page["items"]
                )
                if len(rows) > self.request.policy.max_playlist_items:
                    raise ValueError(
                        "Playlist exceeds configured item limit; "
                        "nothing was truncated"
                    )
                page = client.next(page) if page.get("next") else None
        items = []
        for row in rows:
            if not row or row.get("is_local") or row.get("type") != "track":
                raise ValueError(
                    "Collection includes unavailable or local tracks"
                )
            url = row["external_urls"]["spotify"]
            items.append(
                DownloadItem(
                    url=url,
                    source_url=url,
                    title=row["name"][:200],
                    performer=", ".join(
                        artist["name"] for artist in row["artists"]
                    )[:200],
                    duration=row.get("duration_ms", 0) / 1000 or None,
                    kind="audio",
                    engine="spotify",
                )
            )
        return DownloadPlan(items=items)

    def download(self, item: DownloadItem):
        from yt_dlp import YoutubeDL

        query = (
            "ytsearch5:" + item.title + " " + (item.performer or "") + " audio"
        )
        options: Any = {
            "quiet": True,
            "logger": ExtractorLogger(),
            "extract_flat": True,
            "skip_download": True,
            "socket_timeout": self.request.policy.source_timeout_seconds,
            "cachedir": False,
        }
        with YoutubeDL(options) as downloader:
            result: Any = downloader.extract_info(query, download=False)
        candidates = result.get("entries", []) if result else []
        candidate = next(
            (
                row
                for row in candidates
                if row
                and (
                    not item.duration
                    or not row.get("duration")
                    or abs(row["duration"] - item.duration)
                    < max(15, item.duration * 0.08)
                )
            ),
            None,
        )
        if candidate is None:
            raise ValueError("No matching public audio source found")
        url = (
            candidate.get("webpage_url")
            or "https://www.youtube.com/watch?v=" + candidate["id"]
        )
        resolved = item.model_copy(
            update={"url": url, "source_url": url, "engine": "video"}
        )
        result = VideoDownloader(self.request).download(resolved)
        return result
