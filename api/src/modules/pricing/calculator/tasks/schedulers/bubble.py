from papilio.core.logger import logger
from papilio_tasks.apps.schedulers.backends.redis import (
    RedisQueue,
    RedisScheduler,
)

from src.modules.pricing.calculator.interfaces import IBubbleCalculatorService


class CalculateBubbleTask(RedisScheduler):
    queue = RedisQueue("calculator_queue")

    def __init__(self, service: IBubbleCalculatorService) -> None:
        self.service = service

    async def run(self, bubble_id: int) -> int:
        amount = await self.service.calculate(bubble_id)
        logger.info("bubble %s settled at %s", bubble_id, amount)
        return amount
