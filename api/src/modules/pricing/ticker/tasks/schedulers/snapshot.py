from papilio.core.logger import logger
from papilio_tasks.apps.schedulers.backends.redis import (
    RedisQueue,
    RedisScheduler,
)

from src.modules.pricing.ticker.interfaces import (
    IBubbleSnapshotService,
    IPriceSnapshotService,
    ISourceBubbleSnapshotService,
    ISourcePriceSnapshotService,
)


class SnapshotPricesTask(RedisScheduler):
    schedule = [{"cron": "*/5 * * * *"}]
    queue = RedisQueue("ticker_queue")

    def __init__(self, service: IPriceSnapshotService) -> None:
        self.service = service

    async def run(self) -> bool:
        written = await self.service.snapshot_all()
        logger.info("asset prices snapshotted: %s", written)
        return written


class SnapshotSourcePricesTask(RedisScheduler):
    schedule = [{"cron": "*/5 * * * *"}]
    queue = RedisQueue("ticker_queue")

    def __init__(self, service: ISourcePriceSnapshotService) -> None:
        self.service = service

    async def run(self) -> bool:
        written = await self.service.snapshot_all()
        logger.info("source prices snapshotted: %s", written)
        return written


class SnapshotBubblesTask(RedisScheduler):
    schedule = [{"cron": "*/5 * * * *"}]
    queue = RedisQueue("ticker_queue")

    def __init__(self, service: IBubbleSnapshotService) -> None:
        self.service = service

    async def run(self) -> bool:
        written = await self.service.snapshot_all()
        logger.info("bubble premiums snapshotted: %s", written)
        return written


class SnapshotSourceBubblesTask(RedisScheduler):
    schedule = [{"cron": "*/5 * * * *"}]
    queue = RedisQueue("ticker_queue")

    def __init__(self, service: ISourceBubbleSnapshotService) -> None:
        self.service = service

    async def run(self) -> bool:
        written = await self.service.snapshot_all()
        logger.info("source premiums snapshotted: %s", written)
        return written
