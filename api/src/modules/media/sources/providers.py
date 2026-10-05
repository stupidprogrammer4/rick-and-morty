from dishka import Provider, Scope, provide

from src.modules.media.sources.app.downloads import MediaFileDownloads
from src.modules.media.sources.app.matching import MusicMatching
from src.modules.media.sources.app.music import MusicSourceResolver
from src.modules.media.sources.app.planning import MediaSourcePlanner
from src.modules.media.sources.app.requests import MediaExtractionRequests
from src.modules.media.sources.app.strategy import MediaSourceStrategy
from src.modules.media.sources.app.transfer import MediaSourceTransfer
from src.modules.media.sources.app.youtube import YoutubeSourceResolver
from src.modules.media.sources.infra.downloaders.cobalt import (
    CobaltMediaExtraction,
)
from src.modules.media.sources.infra.downloaders.spotify import SpotifyCatalog
from src.modules.media.sources.infra.extraction import PublicMediaExtraction
from src.modules.media.sources.infra.metadata import MediaMetadataExtraction
from src.modules.media.sources.infra.process import MediaExtractorProcess
from src.modules.media.sources.infra.threads import MediaMetadataThreads
from src.modules.media.sources.infra.transfer import MediaFileTransfer
from src.modules.media.sources.interfaces import (
    IMediaFileDownloads,
    IMediaSourcePlanner,
    IMediaSourceTransfer,
    IMusicSourceResolver,
    IYoutubeSourceResolver,
)


class MediaSourceProvider(Provider):
    scope = Scope.REQUEST
    sources = provide(MediaSourceStrategy)
    requests = provide(MediaExtractionRequests)
    public = provide(PublicMediaExtraction)
    process = provide(MediaExtractorProcess)
    transfer = provide(MediaFileTransfer)
    threads = provide(MediaMetadataThreads, scope=Scope.APP)
    metadata = provide(MediaMetadataExtraction)
    cobalt = provide(CobaltMediaExtraction)
    youtube = provide(YoutubeSourceResolver, provides=IYoutubeSourceResolver)
    matching = provide(MusicMatching)
    music = provide(MusicSourceResolver, provides=IMusicSourceResolver)
    source_transfer = provide(
        MediaSourceTransfer, provides=IMediaSourceTransfer
    )
    spotify = provide(SpotifyCatalog)
    planner = provide(MediaSourcePlanner, provides=IMediaSourcePlanner)
    downloads = provide(MediaFileDownloads, provides=IMediaFileDownloads)
