from pydantic import BaseModel

from src.tools.statistics import StatisticsCriteria, StatisticsSnapshot


class PricingStatisticsCriteria(StatisticsCriteria):
    active: bool
    scheduler_off: bool


class PricingCounts(BaseModel):
    sources: int
    active_sources: int
    failed_sources: int
    assets: int
    scheduler_off_assets: int
    symbols: int


class PricingStatistics(PricingCounts, StatisticsSnapshot):
    pass
