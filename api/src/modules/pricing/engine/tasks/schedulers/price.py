from papilio_tasks.apps.schedulers.backends.redis import (
    RedisScheduler,
)
from papilio_tasks.tools.retry import Retry

from portal_contracts.configuration import MarketEnginePolicy
from src.modules.pricing.engine.domain.push import SupplierPricePush
from src.modules.pricing.engine.domain.quotes import SupplierSourceQuote
from src.modules.pricing.engine.interfaces import IPushRunnerService
from src.shared.dates import utc_now


class PersistSupplierPrice(RedisScheduler):
    retry = Retry(attempts=3, delay=1, errors=(Exception,))

    def __init__(self, runner: IPushRunnerService, policy: MarketEnginePolicy):
        self.runner = runner
        self.policy = policy

    async def run(self, data: dict) -> bool:
        payload = SupplierPricePush.model_validate(data)
        now = utc_now()
        if any(
            (now - quote.quoted_at).total_seconds() < 0
            or (now - quote.quoted_at).total_seconds()
            > self.policy.max_quote_age_seconds
            for quote in payload.quotes
        ):
            raise ValueError("Supplier quote is stale or in the future")
        result = await self.runner.run(
            payload.source,
            [
                SupplierSourceQuote.from_pair(
                    payload.source,
                    quote.symbol,
                    quote.buying_rial,
                    quote.selling_rial,
                    is_closed=quote.is_closed,
                    quoted_at=quote.quoted_at,
                )
                for quote in payload.quotes
            ],
        )
        return result
