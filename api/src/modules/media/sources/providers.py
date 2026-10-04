from dishka import Provider, Scope, provide

from src.modules.media.sources.app.strategy import MediaSourceStrategy
from src.modules.media.sources.infra.downloader import MediaDownloader
from src.modules.media.sources.interfaces import IMediaDownloader


class MediaSourceProvider(Provider):
    scope = Scope.REQUEST
    sources = provide(MediaSourceStrategy)
    downloader = provide(MediaDownloader, provides=IMediaDownloader)
