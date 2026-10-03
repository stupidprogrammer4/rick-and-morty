from dishka import Provider, Scope, provide

from src.modules.ops.app.queries import PortalStatusQuery
from src.modules.ops.app.services import PortalGuardService
from src.modules.ops.infra.mysql import PortalGuardRepository
from src.modules.ops.infra.readers import (
    DatabaseHealthReader,
    QueueStatusReader,
)
from src.modules.ops.interfaces import IPortalGuard, IPortalStatusQuery


class OpsProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(PortalGuardRepository)
    reader = provide(DatabaseHealthReader)
    queues = provide(QueueStatusReader)
    guard = provide(PortalGuardService, provides=IPortalGuard)
    status = provide(PortalStatusQuery, provides=IPortalStatusQuery)
