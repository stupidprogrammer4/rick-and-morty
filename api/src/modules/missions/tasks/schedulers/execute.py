from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from src.modules.missions.interfaces import (
    IMissionExecutor,
    IMissionRecovery,
    IScheduledMissionCommands,
)


class ExecuteMission(RedisScheduler):
    def __init__(self, executor: IMissionExecutor):
        self.executor = executor

    async def run(self, mission_id: int) -> None:
        await self.executor.execute(mission_id)


class RecoverMissions(RedisScheduler):
    schedule = [{"interval": 5}]

    def __init__(self, recovery: IMissionRecovery):
        self.recovery = recovery

    async def run(self) -> None:
        await self.recovery.enqueue_pending()


class ScheduleContent(RedisScheduler):
    schedule = [{"interval": 60}]

    def __init__(self, commands: IScheduledMissionCommands):
        self.commands = commands

    async def run(self) -> None:
        await self.commands.tick()
