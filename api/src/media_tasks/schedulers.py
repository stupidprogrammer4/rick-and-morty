from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from src.modules.media.downloads.interfaces import (
    IMediaCompletion,
    IMediaDelivery,
    IMediaDispatch,
    IMediaDownloadRecorder,
    IMediaMaintenance,
    IMediaPlanner,
    IMediaTransfer,
    IMediaTransferBatch,
)
from src.modules.media.sources.domain.dtos import MediaDownloadOutcome


class ExecuteMedia(RedisScheduler):
    def __init__(self, executor: IMediaPlanner):
        self.executor = executor

    async def run(self, job_id: int) -> None:
        await self.executor.execute(job_id)


class RecoverMedia(RedisScheduler):
    schedule = [{"interval": 30}]

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


class TransferMedia(RedisScheduler):
    def __init__(self, transfer: IMediaTransfer):
        self.transfer = transfer

    async def run(self, item_id: int) -> None:
        await self.transfer.execute(item_id)


class TransferMediaBatch(RedisScheduler):
    def __init__(self, transfer: IMediaTransferBatch):
        self.transfer = transfer

    async def run(self, item_ids: list[int]) -> None:
        await self.transfer.execute(item_ids)


class DispatchMedia(RedisScheduler):
    def __init__(self, dispatch: IMediaDispatch):
        self.dispatcher = dispatch

    async def run(self) -> None:
        await self.dispatcher.dispatch()


class CompleteMedia(RedisScheduler):
    def __init__(self, completion: IMediaCompletion):
        self.completion = completion

    async def run(self, job_id: int) -> None:
        await self.completion.refresh(job_id)


class SendMedia(RedisScheduler):
    def __init__(self, delivery: IMediaDelivery):
        self.delivery = delivery

    async def run(self, job_id: int) -> None:
        await self.delivery.execute(job_id)


class RecordMediaDownload(RedisScheduler):
    def __init__(self, recorder: IMediaDownloadRecorder):
        self.recorder = recorder

    async def run(self, data: MediaDownloadOutcome) -> None:
        await self.recorder.record(data)
