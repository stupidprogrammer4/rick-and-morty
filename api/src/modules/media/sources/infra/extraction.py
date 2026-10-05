from urllib.parse import urlsplit

from src.modules.media.sources.domain.dtos import (
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
)
from src.modules.media.sources.infra.downloaders.instagram import (
    InstagramDownloader,
)
from src.modules.media.sources.infra.downloaders.pinterest import (
    PinterestDownloader,
)


class PublicMediaExtraction:
    async def plan(self, request: DownloadProcessRequest) -> DownloadPlan:
        stage = request.stages[0]
        if stage == "instagram":
            result = await InstagramDownloader(request).plan()
        elif stage == "pinterest":
            result = await PinterestDownloader(request).plan()
        elif stage == "direct":
            result = DownloadPlan(
                items=[
                    DownloadItem(
                        url=request.url,
                        source_url=request.url,
                        engine="direct",
                        title=urlsplit(request.url).path.rsplit("/", 1)[-1][
                            :200
                        ],
                    )
                ]
            )
        else:
            raise ValueError("Source does not support asynchronous extraction")
        return result
