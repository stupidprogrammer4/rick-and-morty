import asyncio
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field

from src.modules.media.sources.domain.dtos import (
    DownloadItem,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.http import MediaHTTP


class CobaltMediaResponse(BaseModel):
    status: Literal["tunnel", "redirect"]
    url: str = Field(max_length=16000)
    filename: str = Field(min_length=1, max_length=1024)


class CobaltMediaExtraction:
    async def resolve(
        self, request: DownloadProcessRequest, item: DownloadItem
    ) -> DownloadItem:
        endpoint = request.policy.youtube_api_url
        if not endpoint:
            raise ValueError("YouTube API is not configured")
        http = MediaHTTP(request)
        quality = max(
            height
            for height in (144, 240, 360, 480, 720, 1080)
            if height <= request.policy.video_height
        )
        async with (
            asyncio.timeout(request.policy.source_timeout_seconds),
            http.session() as session,
        ):
            raw = await http.metadata(
                session,
                "POST",
                endpoint,
                headers={"Accept": "application/json"},
                json={
                    "url": item.url,
                    "downloadMode": "audio"
                    if request.mode == "audio"
                    else "auto",
                    "audioFormat": "mp3",
                    "videoQuality": str(quality),
                    "youtubeVideoCodec": "h264",
                },
            )
        response = CobaltMediaResponse.model_validate_json(raw)
        http.validate(response.url)
        filename = PurePosixPath(response.filename)
        extension = filename.suffix.lower().removeprefix(".")
        if extension not in (
            {"mp3", "m4a"} if request.mode == "audio" else {"mp4"}
        ):
            raise ValueError("YouTube API returned an incompatible file")
        result = item.model_copy(
            update={
                "url": response.url,
                "title": filename.stem[:200],
                "kind": "audio" if request.mode == "audio" else "video",
                "file_extension": extension,
                "headers": {},
            }
        )
        return result
