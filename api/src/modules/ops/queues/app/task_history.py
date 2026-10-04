from datetime import timedelta

from portal_contracts.configuration import PortalConfiguration
from src.modules.ops.queues.infra.task_history import TaskHistoryStore
from src.shared.dates import utc_now


class TaskHistoryMaintenance:
    def __init__(
        self, history: TaskHistoryStore, configuration: PortalConfiguration
    ):
        self.history = history
        self.configuration = configuration

    async def clean(self) -> int:
        before = utc_now() - timedelta(
            seconds=self.configuration.portal.task_history_seconds
        )
        removed = await self.history.prune(before)
        return removed
