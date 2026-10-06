from papilio.core.logger import logger
from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from src.modules.pricing.retention.app.maintenance import (
    CLEANUP_INTERVAL_SECONDS,
    PricingHistoryMaintenance,
)


class PrunePricingHistory(RedisScheduler):
    schedule = [{"interval": CLEANUP_INTERVAL_SECONDS}]

    def __init__(self, maintenance: PricingHistoryMaintenance):
        self.maintenance = maintenance

    async def run(self) -> dict:
        result = await self.maintenance.clean()
        logger.info("pricing history cleanup: %s", result)
        return result
