from dishka import Provider, Scope, provide

from src.modules.ops.queues.app.task_history import TaskHistoryMaintenance
from src.modules.ops.queues.domain.dtos import TaskStreams
from src.modules.ops.queues.infra.task_history import TaskHistoryStore
from src.modules.ops.queues.interfaces import ITaskHistoryMaintenance
from src.modules.ops.queues.tasks.schedulers.maintenance import (
    PruneTaskHistory,
)


class TaskQueueProvider(Provider):
    scope = Scope.REQUEST
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
