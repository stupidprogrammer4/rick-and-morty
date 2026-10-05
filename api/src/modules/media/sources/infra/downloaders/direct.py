import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from papilio.infra.files.reader import FileReader
from papilio.infra.files.writer import FileWriter

from src.modules.media.sources.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.http import (
    MediaBodyReader,
    MediaHTTP,
)
from src.modules.media.sources.infra.downloaders.native import (
    NativeMediaMetadata,
)


class DirectDownloader:
    def __init__(
        self,
        request: DownloadProcessRequest,
        metadata: NativeMediaMetadata | None = None,
    ):
        self.request = request
        self.metadata = metadata

    async def finish(
        self, path: Path, item: DownloadItem, kind: str
    ) -> DownloadedFile:
        if self.metadata is not None:
            result = await self.metadata.finish(path, item, kind)
            return result
        if kind in {"audio", "video"}:
            probe = await self.execute(
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
                30,
            )
            duration = float(
                json.loads(probe).get("format", {}).get("duration", 0)
            )
            if duration > self.request.policy.max_duration_seconds:
                raise ValueError("Media exceeds configured duration limit")
        if (
            kind == "audio"
            or (self.request.mode == "audio" and kind == "video")
        ) and path.suffix not in {".mp3", ".m4a"}:
            output = path.with_suffix(".mp3")
            await self.execute(
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
                    "-fs",
                    str(self.request.policy.max_file_bytes + 1),
                    str(output),
                ],
                self.request.policy.item_timeout_seconds,
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

    async def execute(self, arguments: list[str], timeout: int) -> bytes:
        process = await asyncio.create_subprocess_exec(
            *arguments,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            async with asyncio.timeout(timeout):
                stdout, stderr = await process.communicate()
            if process.returncode:
                raise ValueError(
                    "Media codec failed: "
                    + stderr.decode(errors="replace")[:200]
                )
            return stdout
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    async def download(self, item: DownloadItem) -> DownloadedFile:
        http = MediaHTTP(self.request)
        http.validate(item.url)
        async with http.session() as client:
            async with client.get(
                item.url, headers=item.headers, max_redirects=6
            ) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Media source returned HTTP {response.status}"
                    )
                extension = self.extension(
                    response.headers.get("Content-Type", ""),
                    str(response.url),
                    item.file_extension,
                )
                if item.file_extension and extension != item.file_extension:
                    raise ValueError(
                        "Media type differs from its source filename"
                    )
                maximum = self.request.policy.max_file_bytes
                if (
                    response.content_length is not None
                    and response.content_length > maximum
                ):
                    raise ValueError("Media exceeds the Telegram file limit")
                path = Path(self.request.directory) / (
                    uuid4().hex + "." + extension
                )
                try:
                    reader = MediaBodyReader(response.content, maximum)
                    size = await FileWriter().write_stream(
                        path, FileReader().chunks(reader), mode="xb"
                    )
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
                    result = await self.finish(path, item, kind)
                    return result
                except BaseException:
                    path.unlink(missing_ok=True)
                    raise

    def extension(
        self, content_type: str, url: str, expected: str | None = None
    ) -> str:
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
            "application/ogg": "ogg",
            "application/pdf": "pdf",
        }
        mime = content_type.split(";", 1)[0].strip().lower()
        extension = extensions.get(mime)
        if not mime:
            extension = expected
        if extension is None and mime == "application/octet-stream":
            candidate = urlsplit(url).path.rsplit(".", 1)[-1].lower()
            extension = (
                candidate if candidate in set(extensions.values()) else None
            )
            if extension is None:
                extension = expected
        if extension is None:
            raise ValueError("URL is not a supported media file")
        return extension
