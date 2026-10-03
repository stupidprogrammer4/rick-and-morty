from papilio.core.logger import logger
from papilio_tasks.apps.schedulers.backends.redis import (
    RedisQueue,
    RedisScheduler,
)

from src.modules.pricing.engine.interfaces import IRunnerService


class CrawlAllSourcesTask(RedisScheduler):
    schedule = [{"interval": 30}]
    queue = RedisQueue("engine_queue")

    def __init__(self, service: IRunnerService) -> None:
        self.service = service

    async def run(self) -> bool:
        cached = await self.service.run()
        logger.info("crawl cached readings: %s", cached)
        return cached
