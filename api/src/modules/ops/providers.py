from dishka import Provider, Scope, provide

from src.modules.ops.app.queries import PortalStatusQuery
from src.modules.ops.app.services import PortalGuardService
from src.modules.ops.app.task_history import TaskHistoryMaintenance
from src.modules.ops.domain.dtos import TaskStreams
from src.modules.ops.infra.mysql import PortalGuardRepository
from src.modules.ops.infra.readers import (
    DatabaseHealthReader,
    QueueStatusReader,
)
from src.modules.ops.infra.task_history import TaskHistoryStore
from src.modules.ops.interfaces import (
    IPortalGuard,
    IPortalStatusQuery,
    ITaskHistoryMaintenance,
)
from src.modules.ops.tasks.schedulers.maintenance import PruneTaskHistory


class OpsProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(PortalGuardRepository)
    reader = provide(DatabaseHealthReader)
    queues = provide(QueueStatusReader)
    guard = provide(PortalGuardService, provides=IPortalGuard)
    status = provide(PortalStatusQuery, provides=IPortalStatusQuery)

    history = provide(TaskHistoryStore)
    history_maintenance = provide(
        TaskHistoryMaintenance, provides=ITaskHistoryMaintenance
    )
    prune_history = provide(PruneTaskHistory)

    @provide(scope=Scope.APP)
    def streams(self) -> TaskStreams:
        from src.apps.media import app as media
        from src.apps.scheduler import app as main

        return TaskStreams(
            main=main.settings.queue_name, media=media.settings.queue_name
        )
