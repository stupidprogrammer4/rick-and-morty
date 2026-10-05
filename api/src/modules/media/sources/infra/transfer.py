import asyncio

from src.modules.media.sources.domain.dtos import (
    DownloadedFile,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.direct import DirectDownloader
from src.modules.media.sources.infra.process import MediaExtractorProcess


class MediaFileTransfer:
    def __init__(self, process: MediaExtractorProcess):
        self.process = process

    async def fetch(self, request: DownloadProcessRequest) -> DownloadedFile:
        if request.item is None:
            raise ValueError("Download item is required")
        if request.item.engine == "direct":
            async with asyncio.timeout(request.policy.item_timeout_seconds):
                result = await DirectDownloader(request).download(request.item)
        else:
            raw = await self.process.execute(request)
            result = DownloadedFile.model_validate_json(raw)
        return result
