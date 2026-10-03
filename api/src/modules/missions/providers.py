from dishka import Provider, Scope, provide

from src.modules.missions.app.commands import MissionAdmission
from src.modules.missions.app.execution import MissionExecutor
from src.modules.missions.app.recovery import MissionRecovery
from src.modules.missions.app.services import MissionService
from src.modules.missions.infra.mysql import (
    MissionEventRepository,
    MissionRepository,
)
from src.modules.missions.interfaces import (
    IMissionAdmission,
    IMissionExecutor,
    IMissionRecovery,
    IMissionService,
)
from src.modules.missions.tasks.schedulers.execute import (
    ExecuteMission,
    RecoverMissions,
)


class MissionProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(MissionRepository)
    events = provide(MissionEventRepository)
    missions = provide(MissionService, provides=IMissionService)
    admission = provide(MissionAdmission, provides=IMissionAdmission)
    executor = provide(MissionExecutor, provides=IMissionExecutor)
    recovery = provide(MissionRecovery, provides=IMissionRecovery)
    execute_task = provide(ExecuteMission)
    recovery_task = provide(RecoverMissions)
