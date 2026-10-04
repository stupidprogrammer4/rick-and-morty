from dishka import Provider, Scope, provide

from src.modules.ops.status.app.queries import PortalStatusQuery
from src.modules.ops.status.infra.readers import (
    DatabaseHealthReader,
    QueueStatusReader,
)
from src.modules.ops.status.interfaces import IPortalStatusQuery


class StatusProvider(Provider):
    scope = Scope.REQUEST
    reader = provide(DatabaseHealthReader)
    queues = provide(QueueStatusReader)
    status = provide(PortalStatusQuery, provides=IPortalStatusQuery)
