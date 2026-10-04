from dishka import Provider, Scope, provide

from src.modules.automation.missions.app.commands import MissionAdmission
from src.modules.automation.missions.app.execution import MissionExecutor
from src.modules.automation.missions.app.recovery import MissionRecovery
from src.modules.automation.missions.app.scheduled import (
    ScheduledMissionCommands,
)
from src.modules.automation.missions.app.services import MissionService
from src.modules.automation.missions.infra.mysql import (
    MissionEventRepository,
    MissionRepository,
)
from src.modules.automation.missions.interfaces import (
    IMissionAdmission,
    IMissionExecutor,
    IMissionRecovery,
    IMissionService,
    IScheduledMissionCommands,
)
from src.modules.automation.missions.tasks.schedulers.execute import (
    ExecuteMission,
    RecoverMissions,
    ScheduleContent,
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
    scheduled = provide(
        ScheduledMissionCommands, provides=IScheduledMissionCommands
    )
    schedule_task = provide(ScheduleContent)
