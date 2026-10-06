from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from src.modules.ops.queues.interfaces import ITaskHistoryMaintenance


class PruneTaskHistory(RedisScheduler):
    schedule = [{"interval": 60}]

    def __init__(self, maintenance: ITaskHistoryMaintenance):
        self.maintenance = maintenance

    async def run(self) -> int:
        removed = await self.maintenance.clean()
        return removed
