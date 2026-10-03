from papilio.utils.dates import utc_now

from src.modules.pricing.stats.domain.models import (
    PricingStatistics,
    PricingStatisticsCriteria,
)
from src.modules.pricing.stats.infra.readers import PricingStatisticsReader


class PricingStatisticsQuery:
    def __init__(self, reader: PricingStatisticsReader) -> None:
        self.reader = reader

    async def get(self) -> PricingStatistics:
        at = utc_now()
        criteria = PricingStatisticsCriteria(
            at=at, active=True, scheduler_off=False
        )
        counts = await self.reader.counts(criteria)
        return PricingStatistics(**counts.model_dump(), generated_at=at)
