from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from src.modules.media.interfaces import IMediaExecutor, IMediaMaintenance


class ExecuteMedia(RedisScheduler):
    def __init__(self, executor: IMediaExecutor):
        self.executor = executor

    async def run(self, job_id: int) -> None:
        await self.executor.execute(job_id)


class RecoverMedia(RedisScheduler):
    schedule = [{"interval": 5}]

    def __init__(self, maintenance: IMediaMaintenance):
        self.maintenance = maintenance

    async def run(self) -> None:
        await self.maintenance.recover()


class CleanMedia(RedisScheduler):
    schedule = [{"interval": 300}]

    def __init__(self, maintenance: IMediaMaintenance):
        self.maintenance = maintenance

    async def run(self) -> None:
        await self.maintenance.clean()
