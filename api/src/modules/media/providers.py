from dishka import Provider, Scope, provide

from portal_contracts.configuration import SettingKey, SettingScope
from portal_contracts.media import MediaPolicy
from src.modules.configuration.interfaces import ISettingValueService
from src.modules.media.app.commands import MediaCommands
from src.modules.media.app.execution import MediaExecutor
from src.modules.media.app.maintenance import MediaMaintenance
from src.modules.media.app.queries import MediaQueries
from src.modules.media.app.services import MediaItemService, MediaJobService
from src.modules.media.app.workspace import MediaWorkspace
from src.modules.media.infra.downloader import MediaDownloader
from src.modules.media.infra.files import MediaFiles
from src.modules.media.infra.gateway import MediaGateway
from src.modules.media.infra.mysql import (
    MediaItemRepository,
    MediaJobRepository,
)
from src.modules.media.infra.readers import MediaReader
from src.modules.media.interfaces import (
    IMediaCommands,
    IMediaDownloader,
    IMediaExecutor,
    IMediaGateway,
    IMediaItemService,
    IMediaJobService,
    IMediaMaintenance,
    IMediaQueries,
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
    executor = provide(MediaExecutor, provides=IMediaExecutor)
    maintenance = provide(MediaMaintenance, provides=IMediaMaintenance)
    downloader = provide(MediaDownloader, provides=IMediaDownloader)
    gateway = provide(MediaGateway, provides=IMediaGateway)

    @provide
    async def policy(self, settings: ISettingValueService) -> MediaPolicy:
        row = await settings.get(SettingKey.MEDIA, SettingScope.GLOBAL)
        if row.value is None:
            raise conflict("Media policy has not been seeded")
        return MediaPolicy.model_validate_json(row.value)
