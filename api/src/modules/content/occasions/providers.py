from dishka import Provider, Scope, provide

from src.modules.content.occasions.app.queries import OccasionQueries
from src.modules.content.occasions.app.service import OccasionService
from src.modules.content.occasions.infra.mysql import OccasionRepository
from src.modules.content.occasions.interfaces import (
    IOccasionQueries,
    IOccasionService,
)


class OccasionProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(OccasionRepository)
    service = provide(OccasionService, provides=IOccasionService)
    queries = provide(OccasionQueries, provides=IOccasionQueries)
