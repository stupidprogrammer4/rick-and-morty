from dishka import Provider, Scope, provide

from src.modules.media.library.app.keys import MediaAssetKeys
from src.modules.media.library.app.service import MediaAssetService
from src.modules.media.library.infra.mysql import MediaAssetRepository
from src.modules.media.library.interfaces import IMediaAssetService


class MediaLibraryProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(MediaAssetRepository)
    assets = provide(MediaAssetService, provides=IMediaAssetService)
    keys = provide(MediaAssetKeys)
