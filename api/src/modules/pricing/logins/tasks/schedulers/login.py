from typing import Sequence

from papilio.core.logger import logger
from papilio_tasks.apps.schedulers.backends.redis import (
    RedisQueue,
    RedisScheduler,
)

from src.modules.pricing.logins.app.logins import LOGINS
from src.modules.pricing.logins.interfaces import ISourceLoginService
from src.modules.pricing.sources.domain.enums import SourceCode


class RefreshAllLoginsTask(RedisScheduler):
    schedule = [{"cron": "0 3 * * 5"}]
    queue = RedisQueue("logins_queue")

    def __init__(self, service: ISourceLoginService) -> None:
        self.service = service

    async def run(self) -> int:
        saved = await self.service.login_all()
        logger.info("refreshed %s of %s source logins", saved, len(LOGINS))
        return saved


class RefreshLoginsTask(RedisScheduler):
    queue = RedisQueue("logins_queue")

    def __init__(self, service: ISourceLoginService) -> None:
        self.service = service

    async def run(self, codes: Sequence[SourceCode]) -> int:
        saved = await self.service.login_codes(codes)
        logger.info("refreshed %s of %s requested logins", saved, len(codes))
        return saved
