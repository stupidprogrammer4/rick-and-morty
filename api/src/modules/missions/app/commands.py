from papilio.infra.db.tools.decorators import transactional

from portal_contracts.missions import MissionAccepted, MissionCreate
from src.config.settings import PortalAppSettings
from src.modules.missions.interfaces import IMissionService
from src.modules.ops.interfaces import IPortalGuard
from src.shared.errors import forbidden


class MissionAdmission:
    def __init__(
        self,
        guard: IPortalGuard,
        missions: IMissionService,
        settings: PortalAppSettings,
    ):
        self.guard = guard
        self.missions = missions
        self.settings = settings

    @transactional
    async def accept(self, data: MissionCreate) -> MissionAccepted:
        if (
            data.owner_id not in self.settings.security.admin_ids
            or data.origin_chat_id != data.owner_id
        ):
            raise forbidden()
        await self.guard.lock(f"missions:{data.owner_id}")
        result = await self.missions.create(data)
        return result
