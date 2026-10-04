from dishka import Provider, Scope, provide

from src.modules.ops.guards.app.services import PortalGuardService
from src.modules.ops.guards.infra.mysql import PortalGuardRepository
from src.modules.ops.guards.interfaces import IPortalGuard


class GuardProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(PortalGuardRepository)
    guard = provide(PortalGuardService, provides=IPortalGuard)
