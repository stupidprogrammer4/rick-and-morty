from dishka import Provider, Scope, provide

from src.modules.pricing.retention.app.maintenance import (
    PricingHistoryMaintenance,
)
from src.modules.pricing.retention.infra.history import PricingHistoryStore
from src.modules.pricing.retention.tasks.schedulers.prune import (
    PrunePricingHistory,
)


class PricingRetentionProvider(Provider):
    scope = Scope.REQUEST

    history = provide(PricingHistoryStore)
    maintenance = provide(PricingHistoryMaintenance)
    prune = provide(PrunePricingHistory)
