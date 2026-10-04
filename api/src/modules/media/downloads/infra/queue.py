import asyncio
from collections.abc import Sequence
from datetime import datetime

from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler
from papilio_tasks.apps.schedulers.redis import SchedulerApplication
from taskiq.decor import AsyncTaskiqDecoratedTask

from src.modules.media.sources.domain.dtos import MediaDownloadOutcome


class MediaQueue:
    def __init__(self, app: SchedulerApplication):
        self.app = app

    def task(self, cls: type[RedisScheduler]) -> AsyncTaskiqDecoratedTask:
        task = self.app.broker.find_task(
            f"{cls.__module__}.{cls.__qualname__}"
        )
        if task is None:
            raise RuntimeError("Media task is not registered")
        return task

    async def dispatch(self) -> None:
        from src.media_tasks.schedulers import DispatchMedia

        await self.task(DispatchMedia).kiq()

    async def dispatch_at(self, when: datetime) -> None:
        from src.media_tasks.schedulers import DispatchMedia

        await self.task(DispatchMedia).schedule_by_time(
            self.app.source.native, when
        )

    async def plan_many(self, ids: Sequence[int]) -> None:
        from src.media_tasks.schedulers import ExecuteMedia

        await asyncio.gather(
            *(self.task(ExecuteMedia).kiq(job_id=id) for id in ids)
        )

    async def transfer_many(self, ids: Sequence[int]) -> None:
        from src.media_tasks.schedulers import TransferMediaBatch

        if ids:
            await self.task(TransferMediaBatch).kiq(item_ids=list(ids))

    async def complete_many(self, ids: Sequence[int]) -> None:
        from src.media_tasks.schedulers import CompleteMedia

        await asyncio.gather(
            *(self.task(CompleteMedia).kiq(job_id=id) for id in ids)
        )

    async def deliver_many(self, ids: Sequence[int]) -> None:
        from src.media_tasks.schedulers import SendMedia

        await asyncio.gather(
            *(self.task(SendMedia).kiq(job_id=id) for id in ids)
        )

    async def downloaded(self, data: MediaDownloadOutcome) -> None:
        from src.media_tasks.schedulers import RecordMediaDownload

        await self.task(RecordMediaDownload).kiq(
            data=data.model_dump(mode="json")
        )
