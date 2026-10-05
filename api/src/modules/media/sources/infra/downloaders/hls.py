import asyncio
import shutil
from pathlib import Path
from urllib.parse import urljoin
from uuid import uuid4

import aiohttp
from papilio.infra.files.reader import FileReader
from papilio.infra.files.writer import FileWriter

from src.modules.media.sources.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.http import MediaHTTP
from src.modules.media.sources.infra.downloaders.native import (
    NativeMediaMetadata,
)


class MediaByteBudget:
    def __init__(self, maximum: int):
        self.maximum = maximum
        self.received = 0

    def consume(self, size: int) -> None:
        self.received += size
        if self.received > self.maximum:
            raise ValueError("Media exceeds the Telegram file limit")


class SegmentReader:
    def __init__(self, stream: aiohttp.StreamReader, budget: MediaByteBudget):
        self.stream = stream
        self.budget = budget

    async def read(self, size: int = -1) -> bytes:
        result = await self.stream.read(size)
        self.budget.consume(len(result))
        return result


class HLSMP3Downloads:
    def __init__(
        self, request: DownloadProcessRequest, metadata: NativeMediaMetadata
    ):
        self.request = request
        self.metadata = metadata

    def playlist(self, raw: bytes, url: str) -> list[str]:
        text = raw.decode("utf-8-sig")
        if not text.startswith("#EXTM3U") or "#EXT-X-ENDLIST" not in text:
            raise ValueError("A complete static audio playlist is required")
        if any(
            marker in text
            for marker in (
                "#EXT-X-KEY",
                "#EXT-X-MAP",
                "#EXT-X-BYTERANGE",
                "#EXT-X-STREAM-INF",
            )
        ):
            raise ValueError("Unsupported segmented audio format")
        urls = [
            urljoin(url, line.strip())
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not urls or len(urls) > self.request.policy.hls_max_segments:
            raise ValueError("Audio playlist exceeds its segment limit")
        for segment in urls:
            MediaHTTP.validate(segment)
        return urls

    async def segment(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        url: str,
        path: Path,
        budget: MediaByteBudget,
        headers: dict[str, str],
    ) -> Path:
        async with semaphore, session.get(url, headers=headers) as response:
            if response.status != 200:
                raise ValueError("Audio segment is unavailable")
            if (
                response.content_length is not None
                and response.content_length > budget.maximum
            ):
                raise ValueError("Audio segment exceeds the file limit")
            reader = SegmentReader(response.content, budget)
            size = await FileWriter().write_stream(
                path, FileReader().chunks(reader), mode="xb"
            )
            if not size:
                raise ValueError("Empty audio segment")
        return path

    def join(self, paths: list[Path], output: Path) -> None:
        paths[0].rename(output)
        with output.open("ab") as target:
            for path in paths[1:]:
                with path.open("rb") as source:
                    shutil.copyfileobj(source, target, length=64 * 1024)
                path.unlink()

    async def download(self, item: DownloadItem) -> DownloadedFile:
        http = MediaHTTP(self.request)
        directory = Path(self.request.directory)
        output = directory / (uuid4().hex + ".mp3")
        paths = []
        try:
            async with http.session() as session:
                raw = await http.metadata(
                    session, "GET", item.url, headers=item.headers
                )
                urls = self.playlist(raw, item.url)
                paths = [directory / (uuid4().hex + ".part") for _ in urls]
                semaphore = asyncio.Semaphore(
                    self.request.policy.hls_segment_concurrency
                )
                budget = MediaByteBudget(self.request.policy.max_file_bytes)
                tasks = [
                    asyncio.create_task(
                        self.segment(
                            session, semaphore, url, path, budget, item.headers
                        )
                    )
                    for url, path in zip(urls, paths, strict=True)
                ]
                try:
                    await asyncio.gather(*tasks)
                except BaseException:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    raise
            await self.metadata.threads.run(self.join, paths, output)
            result = await self.metadata.finish(output, item, "audio")
            return result
        except BaseException:
            output.unlink(missing_ok=True)
            raise
        finally:
            for path in paths:
                path.unlink(missing_ok=True)
