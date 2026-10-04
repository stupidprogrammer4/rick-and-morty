from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide

from portal_contracts.configuration import SettingKey, SettingScope
from portal_contracts.media import MediaPolicy
from src.modules.configuration.interfaces import ISettingValueService
from src.modules.media.app.commands import MediaCommands
from src.modules.media.app.completion import MediaCompletion
from src.modules.media.app.delivery import MediaDelivery
from src.modules.media.app.dispatch import MediaDispatch
from src.modules.media.app.maintenance import MediaMaintenance
from src.modules.media.app.planning import MediaPlanner
from src.modules.media.app.queries import MediaQueries
from src.modules.media.app.results import MediaDownloadRecorder
from src.modules.media.app.services import MediaItemService, MediaJobService
from src.modules.media.app.sources import MediaSourceStrategy
from src.modules.media.app.transfer import MediaTransfer
from src.modules.media.app.transfers import MediaTransferBatch
from src.modules.media.app.workspace import MediaWorkspace
from src.modules.media.infra.downloader import MediaDownloader
from src.modules.media.infra.files import MediaFiles
from src.modules.media.infra.gateway import MediaGateway
from src.modules.media.infra.mysql import (
    MediaItemRepository,
    MediaJobRepository,
)
from src.modules.media.infra.queue import MediaQueue
from src.modules.media.infra.readers import MediaReader
from src.modules.media.interfaces import (
    IMediaCommands,
    IMediaCompletion,
    IMediaDelivery,
    IMediaDispatch,
    IMediaDownloader,
    IMediaDownloadRecorder,
    IMediaGateway,
    IMediaItemService,
    IMediaJobService,
    IMediaMaintenance,
    IMediaPlanner,
    IMediaQueries,
    IMediaQueue,
    IMediaTransfer,
    IMediaTransferBatch,
    IMediaWorkspace,
)
from src.shared.errors import conflict


class MediaProvider(Provider):
    scope = Scope.REQUEST
    job_repo = provide(MediaJobRepository)
    item_repo = provide(MediaItemRepository)
    reader = provide(MediaReader)
    files = provide(MediaFiles)
    workspace = provide(MediaWorkspace, provides=IMediaWorkspace)
    jobs = provide(MediaJobService, provides=IMediaJobService)
    items = provide(MediaItemService, provides=IMediaItemService)
    commands = provide(MediaCommands, provides=IMediaCommands)
    queries = provide(MediaQueries, provides=IMediaQueries)
    planner = provide(MediaPlanner, provides=IMediaPlanner)
    transfer = provide(MediaTransfer, provides=IMediaTransfer)
    transfers = provide(MediaTransferBatch, provides=IMediaTransferBatch)
    results = provide(MediaDownloadRecorder, provides=IMediaDownloadRecorder)
    delivery = provide(MediaDelivery, provides=IMediaDelivery)
    completion = provide(MediaCompletion, provides=IMediaCompletion)
    dispatch = provide(MediaDispatch, provides=IMediaDispatch)
    sources = provide(MediaSourceStrategy)
    maintenance = provide(MediaMaintenance, provides=IMediaMaintenance)
    downloader = provide(MediaDownloader, provides=IMediaDownloader)
    gateway = provide(MediaGateway, provides=IMediaGateway)

    @provide(scope=Scope.APP)
    async def queue(self) -> AsyncIterator[IMediaQueue]:
        from src.apps.media import app

        producer = not app.broker.is_worker_process
        if producer:
            await app.connect()
        try:
            yield MediaQueue(app)
        finally:
            if producer:
                await app.stop()

    @provide
    async def policy(self, settings: ISettingValueService) -> MediaPolicy:
        row = await settings.get(SettingKey.MEDIA, SettingScope.GLOBAL)
        if row.value is None:
            raise conflict("Media policy has not been seeded")
        return MediaPolicy.model_validate_json(row.value)
