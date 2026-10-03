from collections.abc import Awaitable
from typing import Protocol

from src.modules.pricing.stats.domain.models import PricingStatistics


class IPricingStatisticsQuery(Protocol):
    def get(self) -> Awaitable[PricingStatistics]: ...
