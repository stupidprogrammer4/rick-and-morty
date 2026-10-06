from papilio.core.logger import logger
from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from src.modules.ops.retention.app.maintenance import BotHistoryMaintenance


class PruneBotHistory(RedisScheduler):
    schedule = [{"interval": 60}]

    def __init__(self, maintenance: BotHistoryMaintenance):
        self.maintenance = maintenance

    async def run(self) -> dict:
        result = await self.maintenance.clean()
        logger.info("bot history cleanup: %s", result)
        return result
