from papilio_tasks.apps.schedulers.backends.redis import (
    RedisScheduler,
)

from src.modules.pricing.calculator.interfaces import IReconcileSchedules


class ReconcileSchedulesTask(RedisScheduler):
    schedule = [{"interval": 20}]

    def __init__(self, command: IReconcileSchedules) -> None:
        self.command = command

    async def run(self) -> int:
        changed = await self.command.execute()
        return changed
