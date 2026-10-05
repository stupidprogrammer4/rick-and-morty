import asyncio

from src.modules.media.sources.domain.dtos import (
    DownloadedFile,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.direct import DirectDownloader
from src.modules.media.sources.infra.downloaders.hls import HLSMP3Downloads
from src.modules.media.sources.infra.downloaders.native import (
    NativeMediaMetadata,
)
from src.modules.media.sources.infra.threads import MediaMetadataThreads
from src.modules.media.sources.infra.transfer import MediaFileTransfer
from src.modules.media.sources.interfaces import (
    IMusicSourceResolver,
    IYoutubeSourceResolver,
)


class MediaSourceTransfer:
    def __init__(
        self,
        transfer: MediaFileTransfer,
        youtube: IYoutubeSourceResolver,
        music: IMusicSourceResolver,
        threads: MediaMetadataThreads,
    ):
        self.transfer = transfer
        self.youtube = youtube
        self.music = music
        self.threads = threads

    async def fetch(self, request: DownloadProcessRequest) -> DownloadedFile:
        if request.item is None:
            raise ValueError("Download item is required")
        if request.item.engine in {"youtube", "spotify"}:
            async with asyncio.timeout(request.policy.item_timeout_seconds):
                if request.item.engine == "spotify":
                    resolved = await self.music.resolve(request, request.item)
                    item = resolved.item
                else:
                    item = await self.youtube.resolve(request, request.item)
                native = NativeMediaMetadata(request, self.threads)
                result = (
                    await HLSMP3Downloads(request, native).download(item)
                    if item.transport == "hls_mp3"
                    else await DirectDownloader(request, native).download(item)
                )
        else:
            result = await self.transfer.fetch(request)
        return result
