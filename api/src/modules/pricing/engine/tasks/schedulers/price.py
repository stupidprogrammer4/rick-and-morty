from papilio_tasks.apps.schedulers.backends.redis import (
    RedisQueue,
    RedisScheduler,
)
from papilio_tasks.tools.retry import Retry

from portal_contracts.configuration import MarketEnginePolicy
from src.modules.pricing.engine.domain.push import SupplierPricePush
from src.modules.pricing.engine.domain.quotes import SupplierSourceQuote
from src.modules.pricing.engine.interfaces import IPushRunnerService
from src.shared.dates import utc_now


class PersistSupplierPrice(RedisScheduler):
    queue = RedisQueue("engine_queue")
    retry = Retry(attempts=3, delay=1, errors=(Exception,))

    def __init__(self, runner: IPushRunnerService, policy: MarketEnginePolicy):
        self.runner = runner
        self.policy = policy

    async def run(self, data: dict) -> bool:
        payload = SupplierPricePush.model_validate(data)
        age = (utc_now() - payload.quoted_at).total_seconds()
        if age < 0 or age > self.policy.max_quote_age_seconds:
            raise ValueError("Supplier quote is stale or in the future")
        result = await self.runner.run(
            payload.source,
            [
                SupplierSourceQuote.from_pair(
                    payload.source,
                    payload.symbol,
                    payload.buying_rial,
                    payload.selling_rial,
                    is_closed=payload.is_closed,
                    quoted_at=payload.quoted_at,
                )
            ],
        )
        return result
