from dishka import Provider, Scope, provide

from src.modules.ops.retention.app.maintenance import BotHistoryMaintenance
from src.modules.ops.retention.infra.cache import VariableCacheStore
from src.modules.ops.retention.infra.history import BotHistoryStore
from src.modules.ops.retention.tasks.schedulers.prune import PruneBotHistory


class BotRetentionProvider(Provider):
    scope = Scope.REQUEST
    history = provide(BotHistoryStore)
    cache = provide(VariableCacheStore)
    maintenance = provide(BotHistoryMaintenance)
    prune = provide(PruneBotHistory)
