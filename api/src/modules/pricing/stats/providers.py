from dishka import Provider, Scope, provide

from src.modules.pricing.stats.app.queries import PricingStatisticsQuery
from src.modules.pricing.stats.infra.readers import PricingStatisticsReader
from src.modules.pricing.stats.interfaces import IPricingStatisticsQuery


class PricingStatisticsProvider(Provider):
    scope = Scope.REQUEST
    reader = provide(PricingStatisticsReader)
    query = provide(PricingStatisticsQuery, provides=IPricingStatisticsQuery)
