from dishka import Provider, Scope, provide

from src.modules.media.sources.app.downloads import MediaFileDownloads
from src.modules.media.sources.app.planning import MediaSourcePlanner
from src.modules.media.sources.app.requests import MediaExtractionRequests
from src.modules.media.sources.app.strategy import MediaSourceStrategy
from src.modules.media.sources.infra.extraction import PublicMediaExtraction
from src.modules.media.sources.infra.process import MediaExtractorProcess
from src.modules.media.sources.infra.transfer import MediaFileTransfer
from src.modules.media.sources.interfaces import (
    IMediaFileDownloads,
    IMediaSourcePlanner,
)


class MediaSourceProvider(Provider):
    scope = Scope.REQUEST
    sources = provide(MediaSourceStrategy)
    requests = provide(MediaExtractionRequests)
    public = provide(PublicMediaExtraction)
    process = provide(MediaExtractorProcess)
    transfer = provide(MediaFileTransfer)
    planner = provide(MediaSourcePlanner, provides=IMediaSourcePlanner)
    downloads = provide(MediaFileDownloads, provides=IMediaFileDownloads)
