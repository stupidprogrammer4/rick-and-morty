import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from src.modules.media.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    DownloadProcessRequest,
)
from src.modules.media.infra.downloaders.network import validate_url


class DirectDownloader:
    def __init__(self, request: DownloadProcessRequest):
        self.request = request

    def finish(
        self, path: Path, item: DownloadItem, kind: str
    ) -> DownloadedFile:
        if kind in {"audio", "video"}:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(path),
                ],
                capture_output=True,
                timeout=30,
                check=True,
            )
            duration = float(
                json.loads(probe.stdout).get("format", {}).get("duration", 0)
            )
            if duration > self.request.policy.max_duration_seconds:
                raise ValueError("Media exceeds configured duration limit")
        if (
            self.request.mode == "audio"
            and kind in {"audio", "video"}
            and path.suffix not in {".mp3", ".m4a"}
        ):
            output = path.with_suffix(".mp3")
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-i",
                    str(path),
                    "-vn",
                    "-threads",
                    "1",
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    str(output),
                ],
                capture_output=True,
                timeout=self.request.policy.item_timeout_seconds,
                check=True,
            )
            path.unlink()
            path = output
            kind = "audio"
        if self.request.mode == "audio" and kind not in {"audio", "video"}:
            raise ValueError("This file has no audio track")
        if path.stat().st_size > self.request.policy.max_file_bytes:
            raise ValueError("Media exceeds Telegram file limit")
        return DownloadedFile(
            filename=path.name,
            kind="audio"
            if kind == "audio"
            else "video"
            if kind == "video"
            else "photo"
            if kind == "photo"
            else "document",
            title=item.title,
            performer=item.performer,
            source_url=item.source_url,
        )

    def download(self, item: DownloadItem) -> DownloadedFile:
        url = item.url
        with httpx.Client(trust_env=False, timeout=25) as client:
            for _ in range(6):
                validate_url(url)
                with client.stream(
                    "GET", url, headers=item.headers
                ) as response:
                    if response.is_redirect:
                        url = str(
                            response.url.join(response.headers["location"])
                        )
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get(
                        "content-type", ""
                    ).split(";", 1)[0]
                    extensions = {
                        "image/jpeg": "jpg",
                        "image/png": "png",
                        "image/webp": "webp",
                        "image/gif": "gif",
                        "video/mp4": "mp4",
                        "video/webm": "webm",
                        "audio/mpeg": "mp3",
                        "audio/mp4": "m4a",
                        "audio/ogg": "ogg",
                        "application/pdf": "pdf",
                    }
                    extension = extensions.get(content_type)
                    if (
                        extension is None
                        and content_type == "application/octet-stream"
                    ):
                        candidate = (
                            urlsplit(url).path.rsplit(".", 1)[-1].lower()
                        )
                        extension = (
                            candidate
                            if candidate in set(extensions.values())
                            else None
                        )
                    if extension is None:
                        raise ValueError("URL is not a supported media file")
                    maximum = self.request.policy.max_file_bytes
                    if (
                        int(response.headers.get("content-length", "0"))
                        > maximum
                    ):
                        raise ValueError("Media exceeds Telegram file limit")
                    filename = uuid4().hex + "." + extension
                    path = Path(self.request.directory) / filename
                    size = 0
                    with path.open("xb") as output:
                        for chunk in response.iter_bytes(65536):
                            size += len(chunk)
                            if size > maximum:
                                raise ValueError(
                                    "Media exceeds Telegram file limit"
                                )
                            output.write(chunk)
                    if not size:
                        raise ValueError("Empty media file")
                    kind = (
                        "photo"
                        if extension in {"jpg", "png", "webp", "gif"}
                        else "audio"
                        if extension in {"mp3", "m4a", "ogg"}
                        else "video"
                        if extension in {"mp4", "webm"}
                        else "document"
                    )
                    return self.finish(path, item, kind)
        raise ValueError("Too many redirects")
