from src.modules.media.sources.domain.dtos import (
    DownloadItem,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.cobalt import (
    CobaltMediaExtraction,
)
from src.modules.media.sources.infra.metadata import MediaMetadataExtraction


class YoutubeSourceResolver:
    def __init__(
        self, cobalt: CobaltMediaExtraction, metadata: MediaMetadataExtraction
    ):
        self.cobalt = cobalt
        self.metadata = metadata

    async def resolve(
        self, request: DownloadProcessRequest, item: DownloadItem
    ) -> DownloadItem:
        if request.policy.youtube_api_url:
            try:
                result = await self.cobalt.resolve(request, item)
                return result
            except Exception:
                pass
        resolved = await self.metadata.resolve(request, item)
        return resolved.item
