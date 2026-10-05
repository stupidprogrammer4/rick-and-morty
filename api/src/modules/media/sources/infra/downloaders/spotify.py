import asyncio
import base64
import json
from urllib.parse import urlsplit

import aiohttp
from bs4 import BeautifulSoup

from src.config.settings import PortalAppSettings
from src.modules.media.sources.domain.dtos import (
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.http import MediaHTTP
from src.modules.media.sources.infra.threads import MediaMetadataThreads


class SpotifyCatalog:
    def __init__(
        self, threads: MediaMetadataThreads, settings: PortalAppSettings
    ):
        self.threads = threads
        self.settings = settings

    def identity(self, url: str) -> tuple[str, str]:
        parsed = urlsplit(url)
        if parsed.hostname != "open.spotify.com":
            raise ValueError(
                "Send an open.spotify.com track, album or playlist"
            )
        parts = parsed.path.strip("/").split("/")
        if parts[0].startswith("intl-"):
            parts = parts[1:]
        if (
            len(parts) != 2
            or parts[0] not in {"track", "album", "playlist"}
            or not parts[1].isalnum()
        ):
            raise ValueError("Send a Spotify track, album or playlist URL")
        return parts[0], parts[1]

    def embedded(self, raw: bytes, kind: str) -> DownloadPlan:
        document = BeautifulSoup(raw, "html.parser")
        node = document.find("script", id="__NEXT_DATA__")
        if node is None:
            raise ValueError("Spotify did not expose public catalog metadata")
        entity = (
            json.loads(node.get_text())
            .get("props", {})
            .get("pageProps", {})
            .get("state", {})
            .get("data", {})
            .get("entity")
        )
        if not entity:
            raise ValueError("Spotify public catalog metadata is unavailable")
        rows = entity.get("trackList")
        if rows is None:
            rows = [entity] if kind == "track" else []
        total = entity.get("totalTracks") or entity.get("total")
        if kind == "playlist" and total is None:
            raise ValueError(
                "Spotify public playlist count is unavailable;"
                " full catalog API access is required"
            )
        if total is not None and int(total) != len(rows):
            raise ValueError(
                "Spotify public collection is incomplete;"
                " nothing was truncated"
            )
        images = entity.get("coverArt", {}).get("sources") or entity.get(
            "visualIdentity", {}
        ).get("image", [])
        cover = images[0].get("url") if images else None
        items = []
        for position, row in enumerate(rows, 1):
            uri = row.get("uri") or row.get("id")
            if not str(uri).startswith("spotify:track:"):
                raise ValueError(
                    "Spotify collection contains an unavailable track"
                )
            url = "https://open.spotify.com/track/" + uri.rsplit(":", 1)[-1]
            artist = row.get("subtitle") or ", ".join(
                artist.get("name", "") for artist in row.get("artists", [])
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
                    cover_url=cover,
                    album=entity.get("name") if kind == "album" else None,
                    track_number=position,
                )
            )
        return DownloadPlan(items=items)

    def public_playlist(self, raw: bytes, identifier: str) -> DownloadPlan:
        document = BeautifulSoup(raw, "html.parser")
        node = document.find("script", id="initialState")
        if node is None:
            raise ValueError("Spotify public playlist metadata is unavailable")
        state = json.loads(base64.b64decode(node.get_text(), validate=True))
        uri = "spotify:playlist:" + identifier
        entity = state.get("entities", {}).get("items", {}).get(uri, {})
        if entity.get("uri") != uri:
            raise ValueError("Spotify did not return the requested playlist")
        content = entity.get("content", {})
        rows = content.get("items", [])
        total = content.get("totalCount")
        if (
            not isinstance(total, int)
            or total != len(rows)
            or content.get("pagingInfo", {}).get("offset", 0) != 0
        ):
            raise ValueError(
                "Spotify public collection is incomplete;"
                " nothing was truncated"
            )
        items = []
        for position, entry in enumerate(rows, 1):
            row = entry.get("itemV2", {}).get("data", {})
            track_uri = row.get("uri", "")
            if (
                row.get("__typename") != "Track"
                or not track_uri.startswith("spotify:track:")
                or row.get("playability", {}).get("playable") is not True
                or not row.get("duration", {}).get("totalMilliseconds")
            ):
                raise ValueError(
                    "Spotify collection contains an unavailable track"
                )
            album = row.get("albumOfTrack", {})
            images = album.get("coverArt", {}).get("sources", [])
            url = (
                "https://open.spotify.com/track/"
                + track_uri.rsplit(":", 1)[-1]
            )
            items.append(
                DownloadItem(
                    url=url,
                    source_url=url,
                    title=row["name"][:200],
                    performer=", ".join(
                        artist["profile"]["name"]
                        for artist in row.get("artists", {}).get("items", [])
                    )[:200],
                    duration=row["duration"]["totalMilliseconds"] / 1000,
                    kind="audio",
                    engine="spotify",
                    album=album.get("name"),
                    cover_url=images[0].get("url") if images else None,
                    track_number=position,
                )
            )
        return DownloadPlan(items=items)

    def tracks(
        self, rows: list[dict], album: dict | None = None
    ) -> list[DownloadItem]:
        items = []
        for row in rows:
            row = row.get("track") or row.get("item") or row
            if (
                row.get("is_local")
                or row.get("type") != "track"
                or not row.get("id")
            ):
                raise ValueError(
                    "Spotify collection contains an unavailable track"
                )
            record = row.get("album") or album or {}
            images = record.get("images") or []
            url = "https://open.spotify.com/track/" + row["id"]
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
                    album=record.get("name"),
                    cover_url=images[0].get("url") if images else None,
                    isrc=row.get("external_ids", {}).get("isrc"),
                    track_number=row.get("track_number"),
                )
            )
        return items

    async def api_page(
        self,
        http: MediaHTTP,
        session: aiohttp.ClientSession,
        url: str,
        token: str,
        offset: int,
    ) -> dict:
        raw = await http.metadata(
            session,
            "GET",
            url,
            headers={"Authorization": "Bearer " + token},
            params={"limit": 50, "offset": offset},
            allow_redirects=False,
        )
        result = await self.threads.run(json.loads, raw)
        return result

    async def official(
        self, request: DownloadProcessRequest, kind: str, identifier: str
    ) -> DownloadPlan:
        http = MediaHTTP(request)
        async with http.session() as session:
            token = self.settings.media.spotify_access_token.get_secret_value()
            if not token:
                raw = await http.metadata(
                    session,
                    "POST",
                    request.policy.spotify_auth_url,
                    auth=aiohttp.BasicAuth(
                        self.settings.media.spotify_client_id.get_secret_value(),
                        self.settings.media.spotify_client_secret.get_secret_value(),
                    ),
                    data={"grant_type": "client_credentials"},
                    allow_redirects=False,
                )
                token = json.loads(raw)["access_token"]
            base = request.policy.spotify_api_url.rstrip("/")
            if kind == "track":
                raw = await http.metadata(
                    session,
                    "GET",
                    base + "/tracks/" + identifier,
                    headers={"Authorization": "Bearer " + token},
                    allow_redirects=False,
                )
                row = await self.threads.run(json.loads, raw)
                items = await self.threads.run(self.tracks, [row])
                return DownloadPlan(items=items)
            album = None
            if kind == "album":
                raw = await http.metadata(
                    session,
                    "GET",
                    base + "/albums/" + identifier,
                    headers={"Authorization": "Bearer " + token},
                    allow_redirects=False,
                )
                album = await self.threads.run(json.loads, raw)
                first = album["tracks"]
                url = base + "/albums/" + identifier + "/tracks"
            else:
                raw = await http.metadata(
                    session,
                    "GET",
                    base + "/playlists/" + identifier,
                    headers={"Authorization": "Bearer " + token},
                    allow_redirects=False,
                )
                playlist = await self.threads.run(json.loads, raw)
                if playlist.get("public") is not True:
                    raise ValueError(
                        "Only public Spotify playlists are supported"
                    )
                url = base + "/playlists/" + identifier + "/items"
                first = await self.api_page(http, session, url, token, 0)
            total = int(first["total"])
            if total > request.policy.max_playlist_items:
                raise ValueError(
                    "Spotify collection exceeds the item limit;"
                    " nothing was truncated"
                )
            first_rows = first.get("items") or []
            if len(first_rows) < min(total, int(first.get("limit") or 50)):
                raise ValueError("Spotify collection has missing items")
            pages = await asyncio.gather(
                *(
                    self.api_page(http, session, url, token, offset)
                    for offset in range(len(first_rows), total, 50)
                )
            )
            rows = first_rows + [
                row for page in pages for row in page.get("items", [])
            ]
            if len(rows) != total or any(
                int(page["total"]) != total for page in pages
            ):
                raise ValueError(
                    "Spotify collection changed or is incomplete;"
                    " retry the request"
                )
            items = await self.threads.run(self.tracks, rows, album)
            return DownloadPlan(items=items)

    async def plan(self, request: DownloadProcessRequest) -> DownloadPlan:
        kind, identifier = self.identity(request.url)
        if self.settings.media.spotify_access_token.get_secret_value() or (
            kind != "playlist"
            and self.settings.media.spotify_client_id.get_secret_value()
            and self.settings.media.spotify_client_secret.get_secret_value()
        ):
            result = await self.official(request, kind, identifier)
        else:
            http = MediaHTTP(request)
            async with http.session() as session:
                raw = await http.metadata(
                    session,
                    "GET",
                    "https://open.spotify.com/"
                    + ("" if kind == "playlist" else "embed/")
                    + kind
                    + "/"
                    + identifier,
                )
            if kind == "playlist":
                result = await self.threads.run(
                    self.public_playlist, raw, identifier
                )
            else:
                result = await self.threads.run(self.embedded, raw, kind)
        if (
            not result.items
            or len(result.items) > request.policy.max_playlist_items
        ):
            raise ValueError(
                "Empty or oversized Spotify collection; nothing was truncated"
            )
        return result
