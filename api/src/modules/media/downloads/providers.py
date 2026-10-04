from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide

from portal_contracts.configuration import SettingKey, SettingScope
from portal_contracts.media import MediaPolicy
from src.modules.media.downloads.app.commands import MediaCommands
from src.modules.media.downloads.app.completion import MediaCompletion
from src.modules.media.downloads.app.delivery import MediaDelivery
from src.modules.media.downloads.app.dispatch import MediaDispatch
from src.modules.media.downloads.app.maintenance import MediaMaintenance
from src.modules.media.downloads.app.planning import MediaPlanner
from src.modules.media.downloads.app.queries import MediaQueries
from src.modules.media.downloads.app.results import MediaDownloadRecorder
from src.modules.media.downloads.app.services import (
    MediaItemService,
    MediaJobService,
)
from src.modules.media.downloads.app.transfer import MediaTransfer
from src.modules.media.downloads.app.transfers import MediaTransferBatch
from src.modules.media.downloads.infra.mysql import (
    MediaItemRepository,
    MediaJobRepository,
)
from src.modules.media.downloads.infra.queue import MediaQueue
from src.modules.media.downloads.infra.readers import MediaReader
from src.modules.media.downloads.interfaces import (
    IMediaCommands,
    IMediaCompletion,
    IMediaDelivery,
    IMediaDispatch,
    IMediaDownloadRecorder,
    IMediaItemService,
    IMediaJobService,
    IMediaMaintenance,
    IMediaPlanner,
    IMediaQueries,
    IMediaQueue,
    IMediaTransfer,
    IMediaTransferBatch,
)
from src.modules.ops.settings.interfaces import ISettingValueService
from src.shared.errors import conflict


class MediaDownloadProvider(Provider):
    scope = Scope.REQUEST
    job_repo = provide(MediaJobRepository)
    item_repo = provide(MediaItemRepository)
    reader = provide(MediaReader)
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
    maintenance = provide(MediaMaintenance, provides=IMediaMaintenance)

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
